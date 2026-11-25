import { Injectable, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import {
  OAuthProvider,
  Prisma,
  TripStatus,
  UserRole,
  YoutubeUpdateScope,
  YoutubeUpdateStatus,
} from '@prisma/client';
import { createHash, randomBytes, randomUUID } from 'crypto';

export const HA_LONG_DESTINATION_ID = 'd1111111-1111-4111-8111-111111111111';
export const DA_NANG_DESTINATION_ID = 'd2222222-2222-4222-8222-222222222222';
export const PHU_QUOC_DESTINATION_ID = 'd3333333-3333-4333-8333-333333333333';
export const THAP_DONG_HO_PLACE_ID = '65562a67-84ff-44a0-990d-31917a2a9bd0';
export const NULL_FIELD_VERIFIED_PLACE_ID =
  '75562a67-84ff-44a0-990d-31917a2a9bd1';
export const UNVERIFIED_PLACE_ID = '00000000-0000-4000-8000-000000000999';

const ATTRACTION_CATEGORY_ID = 'c1111111-1111-4111-8111-111111111111';
const VIEWPOINT_CATEGORY_ID = 'c2222222-2222-4222-8222-222222222222';

const THAP_DONG_HO_COVER =
  'https://thumb.wikimedia.org/wikipedia/commons/thumb/5/5e/C%E1%BB%99t_%C4%90%E1%BB%93ng_H%E1%BB%93_-_Vincom_H%E1%BA%A1_Long_2022.jpg/960px-C%E1%BB%99t_%C4%90%E1%BB%93ng_H%E1%BB%93_-_Vincom_H%E1%BA%A1_Long_2022.jpg?utm_source=commons.wikimedia.org&utm_campaign=imageinfo&utm_content=thumbnail';

interface StoredUser {
  id: string;
  email: string;
  passwordHash: string | null;
  role: UserRole;
  isVerified: boolean;
  tokenVersion: number;
  createdAt: Date;
  updatedAt: Date;
  deletedAt: Date | null;
}

interface StoredProfile {
  id: string;
  userId: string;
  displayName: string;
  avatar: string | null;
  bio: string | null;
  phone: string | null;
  createdAt: Date;
  updatedAt: Date;
}

interface StoredTravelPreference {
  id: string;
  userId: string;
  travelStyle: string | null;
  budgetMin: number | null;
  budgetMax: number | null;
  preferredGroup: string | null;
  interests: string[];
  avoidances: string[];
  dietaryNeeds: string[];
  createdAt: Date;
  updatedAt: Date;
}

interface StoredPasswordResetToken {
  id: string;
  userId: string;
  tokenHash: string;
  expiresAt: Date;
  usedAt: Date | null;
  createdAt: Date;
}

interface StoredOAuthAccount {
  id: string;
  userId: string;
  provider: OAuthProvider;
  providerUserId: string;
  email: string | null;
  createdAt: Date;
  updatedAt: Date;
}

interface StoredDestination {
  id: string;
  name: string;
  nameEn: string | null;
  slug: string;
  description: string | null;
  coverImage: string | null;
  province: string | null;
  region: string | null;
  latitude: number | null;
  longitude: number | null;
  rating: number | null;
  reviewCount: number;
  isPopular: boolean;
  deletedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

interface StoredPlaceCategory {
  id: string;
  name: string;
  icon: string | null;
  color: string | null;
}

interface StoredPlace {
  id: string;
  destinationId: string;
  categoryId: string | null;
  name: string;
  nameEn: string | null;
  description: string | null;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  priceMin: number | null;
  priceMax: number | null;
  openingHours: string | null;
  coverImage: string | null;
  images: string[];
  rating: number | null;
  reviewCount: number;
  deletedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

interface StoredPlaceSource {
  id: string;
  placeId: string;
  sourceName: string;
  sourceId: string;
  rawName: string | null;
  confidenceScore: number | null;
  rawData: Record<string, unknown> | null;
  createdAt: Date;
}

interface StoredDocument {
  id: string;
  placeId: string | null;
  title: string;
  content: string;
  createdAt: Date;
}

interface StoredYoutubePoiUpdate {
  id: string;
  dedupeKey: string;
  source: string;
  channelId: string;
  channelTitle: string | null;
  videoId: string;
  videoUrl: string;
  title: string;
  description: string | null;
  tags: string[];
  latitude: number | null;
  longitude: number | null;
  publishedAt: Date;
  sourceUpdatedAt: Date | null;
  receivedAt: Date;
  lastReceivedAt: Date;
  deliveryCount: number;
  status: YoutubeUpdateStatus;
  scope: YoutubeUpdateScope;
  placeId: string | null;
  destinationId: string | null;
  groundingBasis: string | null;
  decisionReason: string;
  groundingEvidence: unknown;
  rawPayload: unknown;
}

interface StoredTrip {
  id: string;
  userId: string;
  title: string;
  description: string | null;
  destinationId: string | null;
  startDate: Date | null;
  endDate: Date | null;
  totalBudget: number | null;
  currency: string;
  travelStyle: string | null;
  interests: string[];
  status: TripStatus;
  isAiGenerated: boolean;
  deletedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

interface StoredTripMember {
  id: string;
  tripId: string;
  userId: string;
  role: string;
  createdAt: Date;
}

interface StoredItinerary {
  id: string;
  tripId: string;
  dayNumber: number;
  title: string | null;
  date: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

interface StoredItineraryItem {
  id: string;
  itineraryId: string;
  placeId: string | null;
  clientRequestId: string | null;
  orderIndex: number;
  startTime: string | null;
  endTime: string | null;
  activity: string;
  notes: string | null;
  estimatedCost: number | null;
  transportMode: string | null;
  createdAt: Date;
  updatedAt: Date;
}

interface StoredVideo {
  id: string;
  userId: string;
  title: string | null;
  caption: string | null;
  videoUrl: string;
  thumbnailUrl: string | null;
  duration: number | null;
  viewCount: number;
  likeCount: number;
  commentCount: number;
  tags: string[];
  createdAt: Date;
  updatedAt: Date;
  deletedAt: Date | null;
}

interface StringFilter {
  contains?: string;
  equals?: string;
  mode?: 'default' | 'insensitive';
}

const ADDITIONAL_HA_LONG_POIS: ReadonlyArray<{
  name: string;
  nameEn: string;
  lat: number;
  lng: number;
  categoryId: string;
}> = [
  {
    name: 'Bảo tàng Quảng Ninh',
    nameEn: 'Quang Ninh Museum',
    lat: 20.9491,
    lng: 107.1012,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Cung Quy hoạch Hội chợ và Triển lãm Quảng Ninh',
    nameEn: 'Quang Ninh Planning Palace',
    lat: 20.9488,
    lng: 107.1045,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Công viên Hoa Hạ Long',
    nameEn: 'Ha Long Flower Park',
    lat: 20.9554,
    lng: 107.0684,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Cầu Bãi Cháy',
    nameEn: 'Bai Chay Bridge',
    lat: 20.9598,
    lng: 107.0642,
    categoryId: VIEWPOINT_CATEGORY_ID,
  },
  {
    name: 'Bãi tắm Bãi Cháy',
    nameEn: 'Bai Chay Beach',
    lat: 20.9532,
    lng: 107.0431,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Núi Bài Thơ',
    nameEn: 'Poem Mountain',
    lat: 20.9468,
    lng: 107.0789,
    categoryId: VIEWPOINT_CATEGORY_ID,
  },
  {
    name: 'Chùa Long Tiên',
    nameEn: 'Long Tien Pagoda',
    lat: 20.9482,
    lng: 107.0772,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Đền Đức Ông Trần Quốc Nghiễn',
    nameEn: 'Tran Quoc Nghien Temple',
    lat: 20.9455,
    lng: 107.0761,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Chợ Hạ Long 1',
    nameEn: 'Ha Long Market 1',
    lat: 20.9502,
    lng: 107.0731,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Vòng quay Mặt Trời Sun Wheel Hạ Long',
    nameEn: 'Sun Wheel Ha Long',
    lat: 20.9612,
    lng: 107.0672,
    categoryId: VIEWPOINT_CATEGORY_ID,
  },
  {
    name: 'Cáp treo Nữ Hoàng',
    nameEn: 'Queen Cable Car',
    lat: 20.9605,
    lng: 107.0531,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Phố cổ Bãi Cháy',
    nameEn: 'Bai Chay Old Quarter',
    lat: 20.9565,
    lng: 107.0488,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Cảng tàu khách Quốc tế Tuần Châu',
    nameEn: 'Tuan Chau International Marina',
    lat: 20.9165,
    lng: 106.9896,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Bãi biển Tuần Châu',
    nameEn: 'Tuan Chau Beach',
    lat: 20.9192,
    lng: 106.9932,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Động Thiên Cung',
    nameEn: 'Thien Cung Cave',
    lat: 20.9032,
    lng: 107.0221,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Hang Đầu Gỗ',
    nameEn: 'Dau Go Cave',
    lat: 20.9048,
    lng: 107.0235,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Hòn Gà Chọi',
    nameEn: 'Fighting Cock Islet',
    lat: 20.8924,
    lng: 107.0512,
    categoryId: VIEWPOINT_CATEGORY_ID,
  },
  {
    name: 'Đảo Ti Tốp',
    nameEn: 'Titop Island',
    lat: 20.8588,
    lng: 107.0794,
    categoryId: VIEWPOINT_CATEGORY_ID,
  },
  {
    name: 'Hang Sửng Sốt',
    nameEn: 'Sung Sot Cave',
    lat: 20.8442,
    lng: 107.0954,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Hang Luồn',
    nameEn: 'Luon Cave',
    lat: 20.8521,
    lng: 107.0891,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Làng chài Cửa Vạn',
    nameEn: 'Cua Van Floating Village',
    lat: 20.8075,
    lng: 107.1292,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
  {
    name: 'Quảng trường 30 tháng 10',
    nameEn: '30/10 Square',
    lat: 20.9486,
    lng: 107.1028,
    categoryId: ATTRACTION_CATEGORY_ID,
  },
];

function createP2002Error(message: string): Prisma.PrismaClientKnownRequestError {
  return new Prisma.PrismaClientKnownRequestError(message, {
    code: 'P2002',
    clientVersion: '5.22.0',
  });
}

function createP2003Error(message: string): Prisma.PrismaClientKnownRequestError {
  return new Prisma.PrismaClientKnownRequestError(message, {
    code: 'P2003',
    clientVersion: '5.22.0',
  });
}

function matchStringFilter(
  candidate: string | null | undefined,
  filter?: string | StringFilter,
): boolean {
  if (filter === undefined) return true;
  if (typeof filter === 'string') {
    return candidate === filter;
  }
  if (candidate === null || candidate === undefined) return false;
  const insensitive = filter.mode === 'insensitive';
  const hay = insensitive ? candidate.toLowerCase() : candidate;
  if (filter.equals !== undefined) {
    const target = insensitive ? filter.equals.toLowerCase() : filter.equals;
    if (hay !== target) return false;
  }
  if (filter.contains !== undefined) {
    const needle = insensitive
      ? filter.contains.toLowerCase()
      : filter.contains;
    if (!hay.includes(needle)) return false;
  }
  return true;
}

@Injectable()
export class InMemoryPrismaService implements OnModuleInit, OnModuleDestroy {
  private users = new Map<string, StoredUser>();
  private profiles = new Map<string, StoredProfile>();
  private preferences = new Map<string, StoredTravelPreference>();
  private resetTokens = new Map<string, StoredPasswordResetToken>();
  private oauthAccounts = new Map<string, StoredOAuthAccount>();
  private destinations = new Map<string, StoredDestination>();
  private categories = new Map<string, StoredPlaceCategory>();
  private places = new Map<string, StoredPlace>();
  private placeSources: StoredPlaceSource[] = [];
  private documents: StoredDocument[] = [];
  private youtubeUpdates: StoredYoutubePoiUpdate[] = [];
  private trips = new Map<string, StoredTrip>();
  private tripMembers: StoredTripMember[] = [];
  private itineraries = new Map<string, StoredItinerary>();
  private itineraryItems = new Map<string, StoredItineraryItem>();
  private videos = new Map<string, StoredVideo>();
  private txQueue: Promise<unknown> = Promise.resolve();

  constructor() {
    this.seed();
  }

  async onModuleInit(): Promise<void> {
    // No external DB connection in the in-memory E2E harness.
  }

  async onModuleDestroy(): Promise<void> {
    // Nothing to disconnect.
  }

  seed(): void {
    this.users.clear();
    this.profiles.clear();
    this.preferences.clear();
    this.resetTokens.clear();
    this.oauthAccounts.clear();
    this.destinations.clear();
    this.categories.clear();
    this.places.clear();
    this.placeSources = [];
    this.documents = [];
    this.youtubeUpdates = [];
    this.trips.clear();
    this.tripMembers = [];
    this.itineraries.clear();
    this.itineraryItems.clear();
    this.videos.clear();

    const now = new Date('2026-11-24T00:00:00.000Z');

    this.categories.set(ATTRACTION_CATEGORY_ID, {
      id: ATTRACTION_CATEGORY_ID,
      name: 'attraction',
      icon: 'place',
      color: '#0D9488',
    });
    this.categories.set(VIEWPOINT_CATEGORY_ID, {
      id: VIEWPOINT_CATEGORY_ID,
      name: 'viewpoint',
      icon: 'landscape',
      color: '#2563EB',
    });

    this.destinations.set(HA_LONG_DESTINATION_ID, {
      id: HA_LONG_DESTINATION_ID,
      name: 'Hạ Long',
      nameEn: 'Ha Long',
      slug: 'ha-long',
      description: 'Thành phố biển di sản tại tỉnh Quảng Ninh.',
      coverImage: THAP_DONG_HO_COVER,
      province: 'Quảng Ninh',
      region: 'north',
      latitude: 20.9516,
      longitude: 107.0852,
      rating: 0,
      reviewCount: 0,
      isPopular: true,
      deletedAt: null,
      createdAt: now,
      updatedAt: now,
    });
    this.destinations.set(DA_NANG_DESTINATION_ID, {
      id: DA_NANG_DESTINATION_ID,
      name: 'Đà Nẵng',
      nameEn: 'Da Nang',
      slug: 'da-nang',
      description: 'Thành phố biển miền Trung Việt Nam.',
      coverImage: null,
      province: 'Đà Nẵng',
      region: 'central',
      latitude: 16.0544,
      longitude: 108.2022,
      rating: 0,
      reviewCount: 0,
      isPopular: true,
      deletedAt: null,
      createdAt: now,
      updatedAt: now,
    });
    this.destinations.set(PHU_QUOC_DESTINATION_ID, {
      id: PHU_QUOC_DESTINATION_ID,
      name: 'Phú Quốc',
      nameEn: 'Phu Quoc',
      slug: 'phu-quoc',
      description: 'Đảo ngọc thuộc tỉnh Kiên Giang.',
      coverImage: null,
      province: 'Kiên Giang',
      region: 'south',
      latitude: 10.2899,
      longitude: 103.984,
      rating: 0,
      reviewCount: 0,
      isPopular: true,
      deletedAt: null,
      createdAt: now,
      updatedAt: now,
    });

    // 1. Canonical POI: Tháp Đồng Hồ (id sorts after 10000000-... so page 1 limit=20 shows 20 POIs and Tháp Đồng Hồ is beyond page 1).
    this.places.set(THAP_DONG_HO_PLACE_ID, {
      id: THAP_DONG_HO_PLACE_ID,
      destinationId: HA_LONG_DESTINATION_ID,
      categoryId: ATTRACTION_CATEGORY_ID,
      name: 'Tháp Đồng Hồ',
      nameEn: 'Halong Clock Tower',
      description:
        'Cột Đồng Hồ (Tháp Đồng Hồ) nằm tại khu vực trung tâm thành phố Hạ Long cạnh Vincom và tổ hợp Times Garden, là điểm mốc giao thông nối các tuyến đường Lê Thánh Tông, 25 Tháng 4, phố Nhà Thờ và phố Tuệ Tĩnh thuộc khu vực Bạch Đằng.',
      address: 'Lê Thánh Tông, Bạch Đằng, Hạ Long, Quảng Ninh',
      latitude: 20.9516105,
      longitude: 107.0851999,
      priceMin: null,
      priceMax: null,
      openingHours: null,
      coverImage: THAP_DONG_HO_COVER,
      images: [THAP_DONG_HO_COVER],
      rating: null,
      reviewCount: 0,
      deletedAt: null,
      createdAt: now,
      updatedAt: now,
    });
    this.placeSources.push({
      id: 'ps-thap-dong-ho',
      placeId: THAP_DONG_HO_PLACE_ID,
      sourceName: 'osm',
      sourceId: 'way/674228542',
      rawName: 'Tháp Đồng Hồ',
      confidenceScore: 1.0,
      rawData: {
        tags: {
          name: 'Tháp Đồng Hồ',
          amenity: 'clock',
          tourism: 'attraction',
          'addr:street': 'Lê Thánh Tông',
          'addr:suburb': 'Bạch Đằng',
          'addr:city': 'Hạ Long',
        },
      },
      createdAt: now,
    });

    // 2. Verified null-field POI (null openingHours, null rating, null coverImage, null address/description).
    this.places.set(NULL_FIELD_VERIFIED_PLACE_ID, {
      id: NULL_FIELD_VERIFIED_PLACE_ID,
      destinationId: HA_LONG_DESTINATION_ID,
      categoryId: ATTRACTION_CATEGORY_ID,
      name: 'Bến Đoan Hạ Long',
      nameEn: 'Ben Doan Pier',
      description: null,
      address: null,
      latitude: 20.9462,
      longitude: 107.0715,
      priceMin: null,
      priceMax: null,
      openingHours: null,
      coverImage: null,
      images: [],
      rating: null,
      reviewCount: 0,
      deletedAt: null,
      createdAt: now,
      updatedAt: now,
    });
    this.placeSources.push({
      id: 'ps-ben-doan',
      placeId: NULL_FIELD_VERIFIED_PLACE_ID,
      sourceName: 'osm',
      sourceId: 'way/111222333',
      rawName: 'Bến Đoan Hạ Long',
      confidenceScore: 0.95,
      rawData: {
        tags: {
          name: 'Bến Đoan Hạ Long',
          tourism: 'attraction',
        },
      },
      createdAt: now,
    });

    // 3. 22 additional verified Hạ Long POIs (total 24 verified Hạ Long POIs).
    ADDITIONAL_HA_LONG_POIS.forEach((poi, index) => {
      const seq = String(index + 1).padStart(12, '0');
      const placeId = `10000000-0000-4000-8000-${seq}`;
      this.places.set(placeId, {
        id: placeId,
        destinationId: HA_LONG_DESTINATION_ID,
        categoryId: poi.categoryId,
        name: poi.name,
        nameEn: poi.nameEn,
        description: `${poi.name} tại thành phố Hạ Long, Quảng Ninh.`,
        address: 'Hạ Long, Quảng Ninh',
        latitude: poi.lat,
        longitude: poi.lng,
        priceMin: null,
        priceMax: null,
        openingHours: null,
        coverImage: null,
        images: [],
        rating: null,
        reviewCount: 0,
        deletedAt: null,
        createdAt: now,
        updatedAt: now,
      });
      this.placeSources.push({
        id: `ps-hl-${index + 1}`,
        placeId,
        sourceName: 'osm',
        sourceId: `node/${1001 + index}`,
        rawName: poi.name,
        confidenceScore: 0.9,
        rawData: {
          tags: {
            name: poi.name,
            tourism: 'attraction',
            'addr:city': 'Hạ Long',
          },
        },
        createdAt: now,
      });
    });

    // 4. Unverified POI (0 placeSources -> fail-closed 404).
    this.places.set(UNVERIFIED_PLACE_ID, {
      id: UNVERIFIED_PLACE_ID,
      destinationId: HA_LONG_DESTINATION_ID,
      categoryId: ATTRACTION_CATEGORY_ID,
      name: 'Địa Điểm Chưa Xác Minh',
      nameEn: 'Unverified Legacy Place',
      description: null,
      address: null,
      latitude: 20.9535,
      longitude: 107.0875,
      priceMin: null,
      priceMax: null,
      openingHours: null,
      coverImage: null,
      images: [],
      rating: null,
      reviewCount: 0,
      deletedAt: null,
      createdAt: now,
      updatedAt: now,
    });

    // 5. Baseline RAG documents (immutable under R4).
    this.documents = [
      {
        id: 'doc-baseline-1',
        placeId: THAP_DONG_HO_PLACE_ID,
        title: 'Tháp Đồng Hồ Hạ Long — Hồ sơ nguồn W07',
        content: 'Tài liệu nền W07 cho Tháp Đồng Hồ tại trung tâm thành phố Hạ Long.',
        createdAt: now,
      },
      {
        id: 'doc-baseline-2',
        placeId: null,
        title: 'Hạ Long — Tổng quan điểm đến',
        content: 'Tài liệu nền W07 cho điểm đến Hạ Long, Quảng Ninh.',
        createdAt: now,
      },
    ];
  }

  getDbStats(): {
    documentsCount: number;
    placeSourcesCount: number;
    youtubePoiUpdatesCount: number;
  } {
    return {
      documentsCount: this.documents.length,
      placeSourcesCount: this.placeSources.length,
      youtubePoiUpdatesCount: this.youtubeUpdates.length,
    };
  }

  seedExpiredResetToken(email: string): string | null {
    const normalized = email.toLowerCase().trim();
    let targetUser: StoredUser | undefined;
    for (const user of this.users.values()) {
      if (user.email === normalized && user.deletedAt === null) {
        targetUser = user;
        break;
      }
    }
    if (!targetUser) {
      return null;
    }

    const rawToken = `exp-${randomBytes(24).toString('hex')}`;
    const tokenHash = createHash('sha256').update(rawToken).digest('hex');
    const id = randomUUID();
    this.resetTokens.set(id, {
      id,
      userId: targetUser.id,
      tokenHash,
      expiresAt: new Date(Date.now() - 60_000),
      usedAt: null,
      createdAt: new Date(),
    });
    return rawToken;
  }

  async $transaction<T>(fn: (tx: this) => Promise<T>): Promise<T> {
    const run = this.txQueue.then(() => fn(this));
    this.txQueue = run.then(
      () => undefined,
      () => undefined,
    );
    return run;
  }

  private hydrateUser(
    row: StoredUser,
    include?: Record<string, unknown>,
    select?: Record<string, unknown>,
  ): Record<string, unknown> {
    const profile =
      Array.from(this.profiles.values()).find((p) => p.userId === row.id) ??
      null;
    const pref =
      Array.from(this.preferences.values()).find((p) => p.userId === row.id) ??
      null;
    const oauthAccounts = Array.from(this.oauthAccounts.values()).filter(
      (a) => a.userId === row.id,
    );

    if (select) {
      const out: Record<string, unknown> = {};
      if (select.id) out.id = row.id;
      if (select.email) out.email = row.email;
      if (select.role) out.role = row.role;
      if (select.isVerified) out.isVerified = row.isVerified;
      if (select.createdAt) out.createdAt = row.createdAt;
      if (select.updatedAt) out.updatedAt = row.updatedAt;
      if (select.profile) {
        out.profile = profile
          ? {
              displayName: profile.displayName,
              avatar: profile.avatar,
              bio: profile.bio,
              phone: profile.phone,
            }
          : null;
      }
      if (select.preferences) {
        out.preferences = pref;
      }
      if (select.oauthAccounts) {
        out.oauthAccounts = oauthAccounts.map((a) => ({ provider: a.provider }));
      }
      return out;
    }

    return {
      ...row,
      ...(include?.profile ? { profile } : {}),
      ...(include?.preferences ? { preferences: pref } : {}),
      ...(include?.oauthAccounts ? { oauthAccounts } : {}),
    };
  }

  readonly user = {
    findUnique: async (args: {
      where: { id?: string; email?: string };
      include?: Record<string, unknown>;
      select?: Record<string, unknown>;
    }) => {
      let found: StoredUser | undefined;
      if (args.where.id) {
        found = this.users.get(args.where.id);
      } else if (args.where.email) {
        for (const u of this.users.values()) {
          if (u.email === args.where.email) {
            found = u;
            break;
          }
        }
      }
      return found
        ? this.hydrateUser(found, args.include, args.select)
        : null;
    },

    create: async (args: {
      data: {
        email: string;
        passwordHash?: string | null;
        role?: UserRole;
        isVerified?: boolean;
        deletedAt?: Date | null;
        profile?: { create: { displayName: string; avatar?: string | null } };
        oauthAccounts?: {
          create: {
            provider: OAuthProvider;
            providerUserId: string;
            email?: string | null;
          };
        };
      };
      include?: Record<string, unknown>;
    }) => {
      for (const existing of this.users.values()) {
        if (existing.email === args.data.email) {
          throw createP2002Error('Unique constraint failed on email');
        }
      }

      const now = new Date();
      const userId = randomUUID();
      const userRow: StoredUser = {
        id: userId,
        email: args.data.email,
        passwordHash: args.data.passwordHash ?? null,
        role: args.data.role ?? UserRole.USER,
        isVerified: args.data.isVerified ?? false,
        tokenVersion: 0,
        createdAt: now,
        updatedAt: now,
        deletedAt: args.data.deletedAt ?? null,
      };
      this.users.set(userId, userRow);

      if (args.data.profile?.create) {
        const profileId = randomUUID();
        this.profiles.set(profileId, {
          id: profileId,
          userId,
          displayName: args.data.profile.create.displayName,
          avatar: args.data.profile.create.avatar ?? null,
          bio: null,
          phone: null,
          createdAt: now,
          updatedAt: now,
        });
      }

      if (args.data.oauthAccounts?.create) {
        await this.oAuthAccount.create({
          data: {
            userId,
            provider: args.data.oauthAccounts.create.provider,
            providerUserId: args.data.oauthAccounts.create.providerUserId,
            email: args.data.oauthAccounts.create.email ?? null,
          },
        });
      }

      return this.hydrateUser(userRow, args.include);
    },

    update: async (args: {
      where: { id: string };
      data: {
        passwordHash?: string | null;
        isVerified?: boolean;
        tokenVersion?: number | { increment: number };
      };
      include?: Record<string, unknown>;
    }) => {
      const existing = this.users.get(args.where.id);
      if (!existing) {
        throw new Error(`User ${args.where.id} not found`);
      }
      if (args.data.passwordHash !== undefined) {
        existing.passwordHash = args.data.passwordHash;
      }
      if (args.data.isVerified !== undefined) {
        existing.isVerified = args.data.isVerified;
      }
      if (typeof args.data.tokenVersion === 'number') {
        existing.tokenVersion = args.data.tokenVersion;
      } else if (
        args.data.tokenVersion &&
        typeof args.data.tokenVersion === 'object' &&
        'increment' in args.data.tokenVersion
      ) {
        existing.tokenVersion =
          (existing.tokenVersion ?? 0) + args.data.tokenVersion.increment;
      }
      existing.updatedAt = new Date();
      return this.hydrateUser(existing, args.include);
    },
  };

  readonly profile = {
    create: async (args: {
      data: {
        userId: string;
        displayName: string;
        avatar?: string | null;
        bio?: string | null;
      };
    }) => {
      const now = new Date();
      const row: StoredProfile = {
        id: randomUUID(),
        userId: args.data.userId,
        displayName: args.data.displayName,
        avatar: args.data.avatar ?? null,
        bio: args.data.bio ?? null,
        phone: null,
        createdAt: now,
        updatedAt: now,
      };
      this.profiles.set(row.id, row);
      return row;
    },

    upsert: async (args: {
      where: { userId: string };
      create: {
        userId: string;
        displayName: string;
        bio?: string;
        avatar?: string;
      };
      update: { displayName?: string; bio?: string; avatar?: string };
    }) => {
      const existing = Array.from(this.profiles.values()).find(
        (p) => p.userId === args.where.userId,
      );
      if (!existing) {
        return this.profile.create({ data: args.create });
      }
      if (args.update.displayName !== undefined) {
        existing.displayName = args.update.displayName;
      }
      if (args.update.bio !== undefined) {
        existing.bio = args.update.bio;
      }
      if (args.update.avatar !== undefined) {
        existing.avatar = args.update.avatar;
      }
      existing.updatedAt = new Date();
      return existing;
    },
  };

  readonly travelPreference = {
    findUnique: async (args: { where: { userId: string } }) => {
      return (
        Array.from(this.preferences.values()).find(
          (p) => p.userId === args.where.userId,
        ) ?? null
      );
    },

    upsert: async (args: {
      where: { userId: string };
      create: {
        userId: string;
        travelStyle?: string;
        budgetMin?: number;
        budgetMax?: number;
        preferredGroup?: string;
        interests?: string[];
        avoidances?: string[];
        dietaryNeeds?: string[];
      };
      update: {
        travelStyle?: string;
        budgetMin?: number;
        budgetMax?: number;
        preferredGroup?: string;
        interests?: string[];
        avoidances?: string[];
        dietaryNeeds?: string[];
      };
    }) => {
      const existing = Array.from(this.preferences.values()).find(
        (p) => p.userId === args.where.userId,
      );
      const now = new Date();
      if (!existing) {
        const row: StoredTravelPreference = {
          id: randomUUID(),
          userId: args.create.userId,
          travelStyle: args.create.travelStyle ?? null,
          budgetMin: args.create.budgetMin ?? 0,
          budgetMax: args.create.budgetMax ?? 10000000,
          preferredGroup: args.create.preferredGroup ?? null,
          interests: args.create.interests ?? [],
          avoidances: args.create.avoidances ?? [],
          dietaryNeeds: args.create.dietaryNeeds ?? [],
          createdAt: now,
          updatedAt: now,
        };
        this.preferences.set(row.id, row);
        return row;
      }

      if (args.update.travelStyle !== undefined) {
        existing.travelStyle = args.update.travelStyle;
      }
      if (args.update.budgetMin !== undefined) {
        existing.budgetMin = args.update.budgetMin;
      }
      if (args.update.budgetMax !== undefined) {
        existing.budgetMax = args.update.budgetMax;
      }
      if (args.update.preferredGroup !== undefined) {
        existing.preferredGroup = args.update.preferredGroup;
      }
      if (args.update.interests !== undefined) {
        existing.interests = args.update.interests;
      }
      if (args.update.avoidances !== undefined) {
        existing.avoidances = args.update.avoidances;
      }
      if (args.update.dietaryNeeds !== undefined) {
        existing.dietaryNeeds = args.update.dietaryNeeds;
      }
      existing.updatedAt = now;
      return existing;
    },
  };

  readonly passwordResetToken = {
    findUnique: async (args: {
      where: { tokenHash: string };
      include?: { user?: boolean };
    }) => {
      for (const row of this.resetTokens.values()) {
        if (row.tokenHash === args.where.tokenHash) {
          return {
            ...row,
            ...(args.include?.user
              ? { user: this.users.get(row.userId) ?? null }
              : {}),
          };
        }
      }
      return null;
    },

    create: async (args: {
      data: { userId: string; tokenHash: string; expiresAt: Date };
    }) => {
      for (const existing of this.resetTokens.values()) {
        if (existing.tokenHash === args.data.tokenHash) {
          throw createP2002Error('Unique constraint on tokenHash');
        }
      }
      const row: StoredPasswordResetToken = {
        id: randomUUID(),
        userId: args.data.userId,
        tokenHash: args.data.tokenHash,
        expiresAt: args.data.expiresAt,
        usedAt: null,
        createdAt: new Date(),
      };
      this.resetTokens.set(row.id, row);
      return row;
    },

    updateMany: async (args: {
      where: {
        userId?: string;
        tokenHash?: string;
        usedAt?: null;
        expiresAt?: { gt?: Date };
      };
      data: { usedAt: Date };
    }) => {
      let count = 0;
      for (const row of this.resetTokens.values()) {
        if (args.where.userId && row.userId !== args.where.userId) continue;
        if (args.where.tokenHash && row.tokenHash !== args.where.tokenHash) {
          continue;
        }
        if (args.where.usedAt === null && row.usedAt !== null) continue;
        if (
          args.where.expiresAt?.gt &&
          !(row.expiresAt.getTime() > args.where.expiresAt.gt.getTime())
        ) {
          continue;
        }
        row.usedAt = args.data.usedAt;
        count += 1;
      }
      return { count };
    },
  };

  readonly oAuthAccount = {
    findUnique: async (args: {
      where: {
        provider_providerUserId: {
          provider: OAuthProvider;
          providerUserId: string;
        };
      };
      include?: { user?: { include?: Record<string, unknown> } };
    }) => {
      const target = args.where.provider_providerUserId;
      for (const row of this.oauthAccounts.values()) {
        if (
          row.provider === target.provider &&
          row.providerUserId === target.providerUserId
        ) {
          const user = this.users.get(row.userId);
          return {
            ...row,
            ...(args.include?.user
              ? {
                  user: user
                    ? this.hydrateUser(user, args.include.user.include)
                    : null,
                }
              : {}),
          };
        }
      }
      return null;
    },

    create: async (args: {
      data: {
        userId: string;
        provider: OAuthProvider;
        providerUserId: string;
        email?: string | null;
      };
    }) => {
      for (const existing of this.oauthAccounts.values()) {
        if (
          existing.provider === args.data.provider &&
          existing.providerUserId === args.data.providerUserId
        ) {
          throw createP2002Error(
            'Unique constraint on provider + providerUserId',
          );
        }
      }
      const now = new Date();
      const row: StoredOAuthAccount = {
        id: randomUUID(),
        userId: args.data.userId,
        provider: args.data.provider,
        providerUserId: args.data.providerUserId,
        email: args.data.email ?? null,
        createdAt: now,
        updatedAt: now,
      };
      this.oauthAccounts.set(row.id, row);
      return row;
    },

    update: async (args: {
      where: { id: string };
      data: { email?: string | null };
    }) => {
      const existing = this.oauthAccounts.get(args.where.id);
      if (!existing) {
        throw new Error(`OAuthAccount ${args.where.id} not found`);
      }
      if (args.data.email !== undefined) {
        existing.email = args.data.email;
      }
      existing.updatedAt = new Date();
      return existing;
    },
  };

  private filterDestinations(where?: {
    deletedAt?: null;
    region?: string;
    OR?: Array<{
      name?: StringFilter;
      province?: StringFilter;
      nameEn?: StringFilter;
    }>;
  }): StoredDestination[] {
    return Array.from(this.destinations.values()).filter((d) => {
      if (where?.deletedAt === null && d.deletedAt !== null) return false;
      if (where?.region && d.region !== where.region) return false;
      if (where?.OR && where.OR.length > 0) {
        const matched = where.OR.some((clause) => {
          if (clause.name && matchStringFilter(d.name, clause.name)) {
            return true;
          }
          if (
            clause.province &&
            matchStringFilter(d.province, clause.province)
          ) {
            return true;
          }
          if (clause.nameEn && matchStringFilter(d.nameEn, clause.nameEn)) {
            return true;
          }
          return false;
        });
        if (!matched) return false;
      }
      return true;
    });
  }

  readonly destination = {
    findMany: async (
      args: {
        where?: {
          deletedAt?: null;
          isPopular?: boolean;
          region?: string;
          OR?: Array<{
            name?: StringFilter;
            province?: StringFilter;
            nameEn?: StringFilter;
          }>;
        };
        skip?: number;
        take?: number;
        include?: { _count?: { select?: { places?: boolean } } };
      } = {},
    ) => {
      let rows = this.filterDestinations(args.where);
      if (args.where?.isPopular !== undefined) {
        rows = rows.filter((d) => d.isPopular === args.where?.isPopular);
      }
      rows.sort((a, b) => {
        if (a.isPopular !== b.isPopular) return a.isPopular ? -1 : 1;
        return a.slug.localeCompare(b.slug);
      });
      const start = args.skip ?? 0;
      const sliced =
        typeof args.take === 'number'
          ? rows.slice(start, start + args.take)
          : rows.slice(start);
      return sliced.map((d) => {
        const placeCount = Array.from(this.places.values()).filter(
          (p) => p.destinationId === d.id && p.deletedAt === null,
        ).length;
        return {
          ...d,
          ...(args.include?._count ? { _count: { places: placeCount } } : {}),
        };
      });
    },

    count: async (
      args: {
        where?: {
          deletedAt?: null;
          region?: string;
          OR?: Array<{
            name?: StringFilter;
            province?: StringFilter;
            nameEn?: StringFilter;
          }>;
        };
      } = {},
    ) => {
      return this.filterDestinations(args.where).length;
    },

    findUnique: async (args: {
      where: { id?: string; slug?: string; deletedAt?: null };
      include?: { places?: Record<string, unknown> };
    }) => {
      const dest = Array.from(this.destinations.values()).find(
        (d) =>
          (args.where.id && d.id === args.where.id) ||
          (args.where.slug && d.slug === args.where.slug),
      );
      if (!dest) return null;
      if (args.where.deletedAt === null && dest.deletedAt !== null) {
        return null;
      }
      if (args.include?.places) {
        const destPlaces = Array.from(this.places.values())
          .filter((p) => {
            if (p.destinationId !== dest.id || p.deletedAt !== null) {
              return false;
            }
            const sources = this.placeSources.filter((s) => s.placeId === p.id);
            return sources.length > 0;
          })
          .map((p) => ({
            ...p,
            category: p.categoryId
              ? (this.categories.get(p.categoryId) ?? null)
              : null,
            placeSources: this.placeSources
              .filter((s) => s.placeId === p.id && s.sourceName === 'osm')
              .map((s) => ({ rawData: s.rawData })),
          }));
        return { ...dest, places: destPlaces };
      }
      return dest;
    },

    update: async (args: {
      where: { id: string };
      data: { deletedAt?: Date | null };
    }) => {
      const existing = this.destinations.get(args.where.id);
      if (!existing) {
        throw new Error(`Destination ${args.where.id} not found`);
      }
      if (args.data.deletedAt !== undefined) {
        existing.deletedAt = args.data.deletedAt;
      }
      existing.updatedAt = new Date();
      return existing;
    },
  };

  private getPlaceSourcesForPlace(placeId: string): StoredPlaceSource[] {
    return this.placeSources.filter((s) => s.placeId === placeId);
  }

  private filterPlaces(where?: {
    id?: string | { in?: string[] };
    deletedAt?: null;
    destinationId?: string;
    placeSources?: { some?: Record<string, unknown> };
    category?: { name?: StringFilter };
    OR?: Array<{
      name?: StringFilter;
      nameEn?: StringFilter;
      address?: StringFilter;
    }>;
  }): StoredPlace[] {
    return Array.from(this.places.values()).filter((p) => {
      if (where?.id !== undefined) {
        if (typeof where.id === 'string' && p.id !== where.id) return false;
        if (
          typeof where.id === 'object' &&
          Array.isArray(where.id.in) &&
          !where.id.in.includes(p.id)
        ) {
          return false;
        }
      }
      if (where?.deletedAt === null && p.deletedAt !== null) return false;
      if (where?.destinationId && p.destinationId !== where.destinationId) {
        return false;
      }
      if (where?.placeSources?.some) {
        if (this.getPlaceSourcesForPlace(p.id).length === 0) return false;
      }
      if (where?.category?.name) {
        const cat = p.categoryId
          ? (this.categories.get(p.categoryId) ?? null)
          : null;
        if (!cat || !matchStringFilter(cat.name, where.category.name)) {
          return false;
        }
      }
      if (where?.OR && where.OR.length > 0) {
        const matched = where.OR.some((clause) => {
          if (clause.name && matchStringFilter(p.name, clause.name)) {
            return true;
          }
          if (clause.nameEn && matchStringFilter(p.nameEn, clause.nameEn)) {
            return true;
          }
          if (clause.address && matchStringFilter(p.address, clause.address)) {
            return true;
          }
          return false;
        });
        if (!matched) return false;
      }
      return true;
    });
  }

  readonly place = {
    findMany: async (
      args: {
        where?: {
          id?: string | { in?: string[] };
          deletedAt?: null;
          destinationId?: string;
          placeSources?: { some?: Record<string, unknown> };
          category?: { name?: StringFilter };
          OR?: Array<{
            name?: StringFilter;
            nameEn?: StringFilter;
            address?: StringFilter;
          }>;
        };
        skip?: number;
        take?: number;
      } = {},
    ) => {
      const rows = this.filterPlaces(args.where);
      rows.sort((a, b) => {
        const rA = a.rating;
        const rB = b.rating;
        if (rA !== rB) {
          if (rA === null) return 1;
          if (rB === null) return -1;
          return rB - rA;
        }
        if (b.reviewCount !== a.reviewCount) {
          return b.reviewCount - a.reviewCount;
        }
        return a.id.localeCompare(b.id);
      });
      const start = args.skip ?? 0;
      const sliced =
        typeof args.take === 'number'
          ? rows.slice(start, start + args.take)
          : rows.slice(start);

      return sliced.map((p) => {
        const dest = this.destinations.get(p.destinationId) ?? null;
        const cat = p.categoryId
          ? (this.categories.get(p.categoryId) ?? null)
          : null;
        const sources = this.getPlaceSourcesForPlace(p.id);
        return {
          ...p,
          destination: dest
            ? {
                id: dest.id,
                name: dest.name,
                nameEn: dest.nameEn,
                slug: dest.slug,
                province: dest.province,
              }
            : null,
          category: cat,
          placeSources: sources,
          _count: {
            reviews: 0,
            itineraryItems: 0,
            placeSources: sources.length,
          },
        };
      });
    },

    count: async (
      args: {
        where?: {
          deletedAt?: null;
          destinationId?: string;
          placeSources?: { some?: Record<string, unknown> };
          category?: { name?: StringFilter };
          OR?: Array<{
            name?: StringFilter;
            nameEn?: StringFilter;
            address?: StringFilter;
          }>;
        };
      } = {},
    ) => {
      return this.filterPlaces(args.where).length;
    },

    findUnique: async (args: { where: { id: string } }) => {
      const place = this.places.get(args.where.id);
      if (!place) return null;
      const dest = this.destinations.get(place.destinationId) ?? null;
      const cat = place.categoryId
        ? (this.categories.get(place.categoryId) ?? null)
        : null;
      const sources = this.getPlaceSourcesForPlace(place.id);
      return {
        ...place,
        destination: dest,
        category: cat,
        placeSources: sources,
        reviews: [],
        _count: {
          placeSources: sources.length,
        },
      };
    },
  };

  readonly youtubePoiUpdate = {
    findUnique: async (args: { where: { dedupeKey: string } }) => {
      return (
        this.youtubeUpdates.find(
          (u) => u.dedupeKey === args.where.dedupeKey,
        ) ?? null
      );
    },

    create: async (args: { data: Omit<StoredYoutubePoiUpdate, 'id'> }) => {
      if (
        this.youtubeUpdates.some((u) => u.dedupeKey === args.data.dedupeKey)
      ) {
        throw createP2002Error(
          'Unique constraint failed on the fields: (`dedupe_key`)',
        );
      }
      const row: StoredYoutubePoiUpdate = {
        ...args.data,
        id: randomUUID(),
      };
      this.youtubeUpdates.push(row);
      return row;
    },

    update: async (args: {
      where: { dedupeKey: string };
      data: {
        deliveryCount?: { increment: number };
        lastReceivedAt?: Date;
      };
    }) => {
      const idx = this.youtubeUpdates.findIndex(
        (u) => u.dedupeKey === args.where.dedupeKey,
      );
      if (idx < 0) {
        throw new Error(
          `YoutubePoiUpdate not found for dedupeKey ${args.where.dedupeKey}`,
        );
      }
      const current = this.youtubeUpdates[idx];
      const updated: StoredYoutubePoiUpdate = {
        ...current,
        deliveryCount:
          current.deliveryCount + (args.data.deliveryCount?.increment ?? 0),
        lastReceivedAt: args.data.lastReceivedAt ?? current.lastReceivedAt,
      };
      this.youtubeUpdates[idx] = updated;
      return updated;
    },

    findMany: async (args: {
      where: {
        placeId?: string | null;
        destinationId?: string;
        status?: YoutubeUpdateStatus | { in: YoutubeUpdateStatus[] };
        scope?: YoutubeUpdateScope | { in: YoutubeUpdateScope[] };
      };
      orderBy?: Array<Record<string, unknown>>;
      take?: number;
    }) => {
      const filtered = this.youtubeUpdates.filter((u) => {
        if (
          args.where.placeId !== undefined &&
          u.placeId !== args.where.placeId
        ) {
          return false;
        }
        if (
          args.where.destinationId !== undefined &&
          u.destinationId !== args.where.destinationId
        ) {
          return false;
        }
        if (args.where.scope !== undefined) {
          if (
            typeof args.where.scope === 'object' &&
            'in' in args.where.scope
          ) {
            if (!args.where.scope.in.includes(u.scope)) return false;
          } else if (u.scope !== args.where.scope) {
            return false;
          }
        }
        if (args.where.status !== undefined) {
          if (
            typeof args.where.status === 'object' &&
            'in' in args.where.status
          ) {
            if (!args.where.status.in.includes(u.status)) return false;
          } else if (u.status !== args.where.status) {
            return false;
          }
        }
        return true;
      });

      filtered.sort((a, b) => {
        const pDiff = b.publishedAt.getTime() - a.publishedAt.getTime();
        if (pDiff !== 0) return pDiff;
        const aNull = a.sourceUpdatedAt === null;
        const bNull = b.sourceUpdatedAt === null;
        if (aNull !== bNull) {
          return aNull ? 1 : -1;
        }
        if (a.sourceUpdatedAt && b.sourceUpdatedAt) {
          const sDiff =
            b.sourceUpdatedAt.getTime() - a.sourceUpdatedAt.getTime();
          if (sDiff !== 0) return sDiff;
        }
        return b.receivedAt.getTime() - a.receivedAt.getTime();
      });

      return typeof args.take === 'number'
        ? filtered.slice(0, args.take)
        : filtered;
    },
  };

  private hydrateTripDestination(destinationId: string | null) {
    if (!destinationId) return null;
    const dest = this.destinations.get(destinationId);
    if (!dest) return null;
    return {
      id: dest.id,
      name: dest.name,
      nameEn: dest.nameEn,
      coverImage: dest.coverImage,
      province: dest.province,
      region: dest.region,
    };
  }

  private hydrateTripMembers(tripId: string) {
    return this.tripMembers
      .filter((m) => m.tripId === tripId)
      .map((m) => {
        const user = this.users.get(m.userId);
        const profile = user
          ? (Array.from(this.profiles.values()).find(
              (p) => p.userId === user.id,
            ) ?? null)
          : null;
        return {
          ...m,
          user: user
            ? {
                id: user.id,
                email: user.email,
                profile: profile
                  ? {
                      displayName: profile.displayName,
                      avatar: profile.avatar,
                    }
                  : null,
              }
            : null,
        };
      });
  }

  readonly trip = {
    create: async (args: {
      data: {
        userId: string;
        title: string;
        description?: string;
        destinationId?: string;
        startDate?: Date | null;
        endDate?: Date | null;
        totalBudget?: number;
        currency?: string;
        travelStyle?: string;
        interests?: string[];
        status?: TripStatus;
        members?: { create: { userId: string; role: string } };
      };
    }) => {
      const now = new Date();
      const id = randomUUID();
      const row: StoredTrip = {
        id,
        userId: args.data.userId,
        title: args.data.title,
        description: args.data.description ?? null,
        destinationId: args.data.destinationId ?? null,
        startDate: args.data.startDate ?? null,
        endDate: args.data.endDate ?? null,
        totalBudget: args.data.totalBudget ?? null,
        currency: args.data.currency ?? 'VND',
        travelStyle: args.data.travelStyle ?? null,
        interests: args.data.interests ?? [],
        status: args.data.status ?? TripStatus.DRAFT,
        isAiGenerated: false,
        deletedAt: null,
        createdAt: now,
        updatedAt: now,
      };
      this.trips.set(id, row);

      if (args.data.members?.create) {
        this.tripMembers.push({
          id: randomUUID(),
          tripId: id,
          userId: args.data.members.create.userId,
          role: args.data.members.create.role,
          createdAt: now,
        });
      }

      return {
        ...row,
        destination: this.hydrateTripDestination(row.destinationId),
        members: this.hydrateTripMembers(id),
      };
    },

    findMany: async (args: {
      where: {
        deletedAt?: null;
        OR?: Array<{
          userId?: string;
          members?: { some: { userId: string } };
        }>;
      };
    }) => {
      const rows = Array.from(this.trips.values())
        .filter((t) => {
          if (args.where.deletedAt === null && t.deletedAt !== null) {
            return false;
          }
          if (args.where.OR && args.where.OR.length > 0) {
            return args.where.OR.some((clause) => {
              if (clause.userId && t.userId === clause.userId) return true;
              if (clause.members?.some.userId) {
                return this.tripMembers.some(
                  (m) =>
                    m.tripId === t.id &&
                    m.userId === clause.members?.some.userId,
                );
              }
              return false;
            });
          }
          return true;
        })
        .sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());

      return rows.map((t) => ({
        ...t,
        destination: this.hydrateTripDestination(t.destinationId),
        _count: {
          members: this.tripMembers.filter((m) => m.tripId === t.id).length,
          itineraries: Array.from(this.itineraries.values()).filter(
            (it) => it.tripId === t.id,
          ).length,
        },
      }));
    },

    findFirst: async (args: {
      where: { id: string; deletedAt?: null; userId?: string };
      include?: Record<string, unknown>;
    }) => {
      const trip = this.trips.get(args.where.id);
      if (!trip) return null;
      if (args.where.deletedAt === null && trip.deletedAt !== null) return null;
      if (args.where.userId && trip.userId !== args.where.userId) return null;

      const tripItineraries = Array.from(this.itineraries.values())
        .filter((it) => it.tripId === trip.id)
        .sort((a, b) => a.dayNumber - b.dayNumber)
        .map((it) => {
          const items = Array.from(this.itineraryItems.values())
            .filter((item) => item.itineraryId === it.id)
            .sort((a, b) => a.orderIndex - b.orderIndex)
            .map((item) => {
              const place = item.placeId
                ? (this.places.get(item.placeId) ?? null)
                : null;
              return {
                ...item,
                place: place
                  ? {
                      id: place.id,
                      name: place.name,
                      address: place.address,
                      coverImage: place.coverImage,
                    }
                  : null,
              };
            });
          return { ...it, items };
        });

      return {
        ...trip,
        destination: this.hydrateTripDestination(trip.destinationId),
        itineraries: tripItineraries,
        members: this.hydrateTripMembers(trip.id),
      };
    },

    update: async (args: {
      where: { id: string };
      data: Partial<StoredTrip>;
    }) => {
      const existing = this.trips.get(args.where.id);
      if (!existing) {
        throw new Error(`Trip ${args.where.id} not found`);
      }
      Object.assign(existing, args.data, { updatedAt: new Date() });
      return {
        ...existing,
        destination: this.hydrateTripDestination(existing.destinationId),
      };
    },
  };

  readonly itinerary = {
    upsert: async (args: {
      where: { tripId_dayNumber: { tripId: string; dayNumber: number } };
      create: {
        tripId: string;
        dayNumber: number;
        title?: string;
        date?: Date | null;
      };
      update: { title?: string; date?: Date | null };
    }) => {
      const existing = Array.from(this.itineraries.values()).find(
        (it) =>
          it.tripId === args.where.tripId_dayNumber.tripId &&
          it.dayNumber === args.where.tripId_dayNumber.dayNumber,
      );
      const now = new Date();
      if (existing) {
        if (args.update.title !== undefined) existing.title = args.update.title;
        if (args.update.date !== undefined) existing.date = args.update.date;
        existing.updatedAt = now;
        return existing;
      }
      const row: StoredItinerary = {
        id: randomUUID(),
        tripId: args.create.tripId,
        dayNumber: args.create.dayNumber,
        title: args.create.title ?? null,
        date: args.create.date ?? null,
        createdAt: now,
        updatedAt: now,
      };
      this.itineraries.set(row.id, row);
      return row;
    },

    deleteMany: async (args: { where: { tripId: string } }) => {
      let count = 0;
      for (const [id, it] of this.itineraries.entries()) {
        if (it.tripId === args.where.tripId) {
          this.itineraries.delete(id);
          count += 1;
        }
      }
      return { count };
    },
  };

  readonly itineraryItem = {
    count: async (args: { where: { itineraryId: string } }) => {
      return Array.from(this.itineraryItems.values()).filter(
        (item) => item.itineraryId === args.where.itineraryId,
      ).length;
    },

    create: async (args: {
      data: {
        itineraryId: string;
        placeId?: string;
        clientRequestId?: string;
        orderIndex: number;
        startTime?: string;
        endTime?: string;
        activity: string;
        notes?: string;
        estimatedCost?: number;
        transportMode?: string;
      };
    }) => {
      if (args.data.clientRequestId) {
        const dup = Array.from(this.itineraryItems.values()).find(
          (item) =>
            item.itineraryId === args.data.itineraryId &&
            item.clientRequestId === args.data.clientRequestId,
        );
        if (dup) {
          throw createP2002Error(
            'Unique constraint failed on (itineraryId, clientRequestId)',
          );
        }
      }
      const now = new Date();
      const row: StoredItineraryItem = {
        id: randomUUID(),
        itineraryId: args.data.itineraryId,
        placeId: args.data.placeId ?? null,
        clientRequestId: args.data.clientRequestId ?? null,
        orderIndex: args.data.orderIndex,
        startTime: args.data.startTime ?? null,
        endTime: args.data.endTime ?? null,
        activity: args.data.activity,
        notes: args.data.notes ?? null,
        estimatedCost: args.data.estimatedCost ?? null,
        transportMode: args.data.transportMode ?? null,
        createdAt: now,
        updatedAt: now,
      };
      this.itineraryItems.set(row.id, row);
      const place = row.placeId
        ? (this.places.get(row.placeId) ?? null)
        : null;
      return {
        ...row,
        place: place
          ? {
              id: place.id,
              name: place.name,
              address: place.address,
            }
          : null,
      };
    },

    findFirst: async (args: {
      where: {
        id?: string;
        itineraryId?: string;
        clientRequestId?: string;
        itinerary?: { tripId: string };
      };
      orderBy?: { orderIndex?: 'asc' | 'desc' };
      select?: Record<string, boolean>;
      include?: Record<string, unknown>;
    }) => {
      const matches = Array.from(this.itineraryItems.values()).filter(
        (item) => {
          if (args.where.id && item.id !== args.where.id) return false;
          if (
            args.where.itineraryId &&
            item.itineraryId !== args.where.itineraryId
          ) {
            return false;
          }
          if (
            args.where.clientRequestId !== undefined &&
            item.clientRequestId !== args.where.clientRequestId
          ) {
            return false;
          }
          if (args.where.itinerary?.tripId) {
            const it = this.itineraries.get(item.itineraryId);
            if (!it || it.tripId !== args.where.itinerary.tripId) return false;
          }
          return true;
        },
      );
      if (matches.length === 0) return null;
      if (args.orderBy?.orderIndex === 'desc') {
        matches.sort((a, b) => b.orderIndex - a.orderIndex);
      } else if (args.orderBy?.orderIndex === 'asc') {
        matches.sort((a, b) => a.orderIndex - b.orderIndex);
      }
      const item = matches[0];
      const place = item.placeId
        ? (this.places.get(item.placeId) ?? null)
        : null;
      if (args.select) {
        const selected: Record<string, unknown> = {};
        for (const [k, enabled] of Object.entries(args.select)) {
          if (enabled && k in item) {
            selected[k] = item[k as keyof StoredItineraryItem];
          }
        }
        return selected;
      }
      return {
        ...item,
        ...(args.include?.place
          ? {
              place: place
                ? {
                    id: place.id,
                    name: place.name,
                    address: place.address,
                  }
                : null,
            }
          : {}),
      };
    },

    delete: async (args: { where: { id: string } }) => {
      const item = this.itineraryItems.get(args.where.id);
      if (!item) {
        throw new Error(`ItineraryItem ${args.where.id} not found`);
      }
      this.itineraryItems.delete(args.where.id);
      return item;
    },

    deleteMany: async (args: { where: { itinerary?: { tripId: string } } }) => {
      const targetTripId = args.where.itinerary?.tripId;
      let count = 0;
      for (const [id, item] of this.itineraryItems.entries()) {
        if (targetTripId) {
          const it = this.itineraries.get(item.itineraryId);
          if (!it || it.tripId !== targetTripId) continue;
        }
        this.itineraryItems.delete(id);
        count += 1;
      }
      return { count };
    },
  };

  readonly tripMember = {
    create: async (args: {
      data: { tripId: string; userId: string; role: string };
    }) => {
      if (
        this.tripMembers.some(
          (m) =>
            m.tripId === args.data.tripId && m.userId === args.data.userId,
        )
      ) {
        throw createP2002Error('Unique constraint on tripId + userId');
      }
      const row: StoredTripMember = {
        id: randomUUID(),
        tripId: args.data.tripId,
        userId: args.data.userId,
        role: args.data.role,
        createdAt: new Date(),
      };
      this.tripMembers.push(row);
      const user = this.users.get(row.userId);
      const profile = user
        ? (Array.from(this.profiles.values()).find(
            (p) => p.userId === user.id,
          ) ?? null)
        : null;
      return {
        ...row,
        user: user
          ? {
              id: user.id,
              email: user.email,
              profile: profile
                ? { displayName: profile.displayName, avatar: profile.avatar }
                : null,
            }
          : null,
      };
    },
  };

  readonly video = {
    findMany: async (args: {
      where?: { deletedAt?: null };
      orderBy?: { createdAt?: 'asc' | 'desc' };
      skip?: number;
      take?: number;
    } = {}) => {
      const rows = Array.from(this.videos.values())
        .filter((v) =>
          args.where?.deletedAt === null ? v.deletedAt === null : true,
        )
        .sort((a, b) =>
          args.orderBy?.createdAt === 'asc'
            ? a.createdAt.getTime() - b.createdAt.getTime()
            : b.createdAt.getTime() - a.createdAt.getTime(),
        );
      const start = args.skip ?? 0;
      return typeof args.take === 'number'
        ? rows.slice(start, start + args.take)
        : rows.slice(start);
    },

    findUnique: async (args: { where: { id: string } }) => {
      return this.videos.get(args.where.id) ?? null;
    },

    create: async (args: {
      data: {
        userId: string;
        videoUrl: string;
        title?: string | null;
        caption?: string | null;
        thumbnailUrl?: string | null;
        duration?: number | null;
        tags?: string[];
      };
    }) => {
      const user = this.users.get(args.data.userId);
      if (!user || user.deletedAt !== null) {
        throw createP2003Error('Foreign key constraint failed on user_id');
      }
      const now = new Date();
      const row: StoredVideo = {
        id: randomUUID(),
        userId: args.data.userId,
        title: args.data.title ?? null,
        caption: args.data.caption ?? null,
        videoUrl: args.data.videoUrl,
        thumbnailUrl: args.data.thumbnailUrl ?? null,
        duration: args.data.duration ?? null,
        viewCount: 0,
        likeCount: 0,
        commentCount: 0,
        tags: args.data.tags ?? [],
        createdAt: now,
        updatedAt: now,
        deletedAt: null,
      };
      this.videos.set(row.id, row);
      return row;
    },
  };

  // R4 Governance traps: YouTube ingestion or any non-RAG flow MUST NEVER mutate documents or place_sources.
  private rejectR4Mutation(target: string): never {
    throw new Error(
      `R4 VIOLATION: Forbidden mutation attempted against ${target} in E2E harness`,
    );
  }

  readonly document = {
    count: async () => this.documents.length,
    create: () => this.rejectR4Mutation('documents'),
    createMany: () => this.rejectR4Mutation('documents'),
    update: () => this.rejectR4Mutation('documents'),
    updateMany: () => this.rejectR4Mutation('documents'),
    upsert: () => this.rejectR4Mutation('documents'),
    delete: () => this.rejectR4Mutation('documents'),
    deleteMany: () => this.rejectR4Mutation('documents'),
  };

  readonly placeSource = {
    count: async () => this.placeSources.length,
    create: () => this.rejectR4Mutation('place_sources'),
    createMany: () => this.rejectR4Mutation('place_sources'),
    update: () => this.rejectR4Mutation('place_sources'),
    updateMany: () => this.rejectR4Mutation('place_sources'),
    upsert: () => this.rejectR4Mutation('place_sources'),
    delete: () => this.rejectR4Mutation('place_sources'),
    deleteMany: () => this.rejectR4Mutation('place_sources'),
  };

  $executeRaw = (): never => this.rejectR4Mutation('raw SQL');
  $executeRawUnsafe = (): never => this.rejectR4Mutation('raw SQL');
}
