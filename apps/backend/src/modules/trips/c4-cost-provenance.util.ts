/**
 * C4 Strict Cost Provenance & Audience-Aware Price Verification Utility.
 *
 * Core invariants:
 * 1. Matching `placeId` ONLY confirms place identity — it NEVER by itself verifies `estimatedCost`.
 * 2. An item is classified as `'VERIFIED'` ("Đã xác minh") ONLY when:
 *    - `estimatedCost` is a non-negative finite integer, AND
 *    - `placeId` resolves to a verified POI that carries authoritative price provenance
 *      (`isVerifiedPrice === true` + non-empty `sourceUrl`), AND
 *    - Either:
 *      (a) `pricingMode === 'FREE'` (universal 0đ admission with official source) and `estimatedCost === 0`, OR
 *      (b) An explicit applicable traveler audience (`adult` / `student` / `child` / `senior` /
 *          `resident_danang` / `infant_free`) and party size are established, and `estimatedCost`
 *          equals `allowedUnitPrice * partySize` for that exact audience (with route/area ticket
 *          deduplication across shared `ticketGroupId` within the same day).
 * 3. Historical/seed `places.priceMin` / `places.priceMax` columns without curated price provenance,
 *    unmatched places, mismatched amounts/audiences, unverified `0đ` items, and legacy saved
 *    `itinerary_items` lacking verified price+audience provenance are ALWAYS classified as
 *    `'ESTIMATED'` ("Tạm tính"), NEVER `'VERIFIED'`.
 * 4. `estimatedCost === null` or `undefined` is ALWAYS classified as `'UNKNOWN'` ("Chưa biết giá").
 */

export type ItemCostProvenanceStatus = 'VERIFIED' | 'ESTIMATED' | 'UNKNOWN';

export type TravelerAudienceCategory =
  | 'adult'
  | 'student'
  | 'child'
  | 'senior'
  | 'resident_danang'
  | 'infant_free';

export type CuratedPricingMode =
  | 'SINGLE_POI'
  | 'FREE'
  | 'ROUTE_TICKET'
  | 'AREA_TICKET'
  | 'UNVERIFIED';

export interface VerifiedPlacePricingRule {
  placeId: string;
  pricingMode: CuratedPricingMode;
  isVerifiedPrice: boolean;
  sourceUrl: string | null;
  checkedDate: string;
  /** Allowed verified per-person unit prices (VND) keyed by traveler audience category. */
  audienceUnitPrices?: Partial<Record<TravelerAudienceCategory, number[]>>;
  /** Shared ticket group ID for route/area tickets so multi-stop visits do not verify double-charging. */
  ticketGroupId?: string;
}

export interface PlaceProvenanceSourceRow {
  sourceName?: string | null;
  rawData?: unknown;
}

export interface ParsedAudienceContext {
  partySize: number;
  audience: TravelerAudienceCategory | null;
  audienceLabelVi: string | null;
  isAudienceExplicit: boolean;
}

export interface CostProvenanceBreakdown {
  verifiedPlaceCostTotal: number;
  verifiedPlaceCostItemCount: number;
  verifiedFreeItemCount: number;
  unverifiedAiEstimatedCostTotal: number;
  unverifiedAiEstimatedItemCount: number;
  unknownCostItemCount: number;
}

export interface ClassifiedCostItemResult {
  costStatus: ItemCostProvenanceStatus;
  costBadgeVi: string;
  isVerifiedFree: boolean;
  costSourceVerified: boolean;
  verifiedSourceUrl: string | null;
  provenanceNoteTag: string | null;
}

const VERIFIED_NOTE_MARKER_RE =
  /\[Nguồn giá đã xác minh:\s*([^\]]+)\]/i;

const VIET_NUMBER_WORDS: Record<string, number> = {
  một: 1,
  mot: 1,
  hai: 2,
  ba: 3,
  bốn: 4,
  bon: 4,
  tư: 4,
  năm: 5,
  nam: 5,
  sáu: 6,
  sau: 6,
  bảy: 7,
  tám: 8,
  chín: 9,
  mười: 10,
};

const AUDIENCE_LABELS_VI: Record<TravelerAudienceCategory, string> = {
  adult: 'người lớn',
  student: 'sinh viên',
  child: 'trẻ em/học sinh',
  senior: 'người cao tuổi',
  resident_danang: 'thường trú Đà Nẵng',
  infant_free: 'trẻ nhỏ miễn phí',
};

/**
 * Authoritative Lô 1 curated pricing & audience-tier rules (checked 2026-11-27,
 * mirrored from `lo1_16_verified_pricing_manifest_v1.json`).
 * Note: POIs with `isVerifiedPrice: false` (e.g. Tháp Đồng Hồ `65562a67-...`,
 * Cảng tàu khách quốc tế Hạ Long `871a6ee7-...`, Chợ Hạ Long II `6215446b-...`,
 * Bến du thuyền Cá Heo `62a874a9-...`) are explicitly marked unverified.
 */
export const CURATED_LO1_VERIFIED_PRICING: Readonly<
  Record<string, VerifiedPlacePricingRule>
> = {
  // Bảo tàng Quảng Ninh — NQ 131/2018/NQ-HĐND
  '8f2b5a69-1293-4efe-8fc5-3a74193edd0f': {
    placeId: '8f2b5a69-1293-4efe-8fc5-3a74193edd0f',
    pricingMode: 'SINGLE_POI',
    isVerifiedPrice: true,
    sourceUrl: 'https://baotangthuvienquangninh.vn/vi',
    checkedDate: '2026-11-27',
    audienceUnitPrices: {
      adult: [40000],
      student: [20000],
      child: [10000],
      infant_free: [0],
    },
  },
  // Tháp Đồng Hồ Hạ Long — chưa xác minh giá
  '65562a67-84ff-44a0-990d-31917a2a9bd0': {
    placeId: '65562a67-84ff-44a0-990d-31917a2a9bd0',
    pricingMode: 'UNVERIFIED',
    isVerifiedPrice: false,
    sourceUrl: null,
    checkedDate: '2026-11-27',
  },
  // Vịnh Hạ Long — vé tuyến VHL1..VHL8
  'ade2140c-7945-4044-b99a-b1a028edce9e': {
    placeId: 'ade2140c-7945-4044-b99a-b1a028edce9e',
    pricingMode: 'ROUTE_TICKET',
    isVerifiedPrice: true,
    sourceUrl: 'https://halongbay.com.vn/p/58-muc-phi-tham-quan-vinh-ha-long',
    checkedDate: '2026-11-27',
    ticketGroupId: 'HALONG_BAY_ROUTE_VHL1',
    audienceUnitPrices: {
      adult: [250000, 200000, 150000, 600000, 70000, 550000, 750000, 500000, 650000],
      senior: [125000, 100000, 75000, 300000, 35000],
      child: [200000, 160000, 120000, 480000, 56000],
      infant_free: [0],
    },
  },
  // Động Thiên Cung — vé tuyến VHL1/VHL5/VHL7 dùng chung
  '9a979427-a0bb-421d-b75f-2a6ee79b120b': {
    placeId: '9a979427-a0bb-421d-b75f-2a6ee79b120b',
    pricingMode: 'ROUTE_TICKET',
    isVerifiedPrice: true,
    sourceUrl: 'https://halongbay.com.vn/p/58-muc-phi-tham-quan-vinh-ha-long',
    checkedDate: '2026-11-27',
    ticketGroupId: 'HALONG_BAY_ROUTE_VHL1',
    audienceUnitPrices: {
      adult: [250000, 600000],
      senior: [125000, 300000],
      child: [200000, 480000],
      infant_free: [0],
    },
  },
  // Hang Đầu Gỗ — vé tuyến VHL1/VHL5/VHL7 dùng chung
  '9fbcb0b4-27bc-4482-a8e3-8be6e3c72677': {
    placeId: '9fbcb0b4-27bc-4482-a8e3-8be6e3c72677',
    pricingMode: 'ROUTE_TICKET',
    isVerifiedPrice: true,
    sourceUrl: 'https://halongbay.com.vn/p/58-muc-phi-tham-quan-vinh-ha-long',
    checkedDate: '2026-11-27',
    ticketGroupId: 'HALONG_BAY_ROUTE_VHL1',
    audienceUnitPrices: {
      adult: [250000, 600000],
      senior: [125000, 300000],
      child: [200000, 480000],
      infant_free: [0],
    },
  },
  // Tổ hợp giải trí Sun World Hạ Long
  '1a95430d-289d-4663-91b8-ae64ede4f9a4': {
    placeId: '1a95430d-289d-4663-91b8-ae64ede4f9a4',
    pricingMode: 'SINGLE_POI',
    isVerifiedPrice: true,
    sourceUrl: 'https://sunworld.vn/operations',
    checkedDate: '2026-11-27',
    audienceUnitPrices: {
      adult: [380000, 369000],
      child: [280000, 272000],
      infant_free: [0],
    },
  },
  // Cảng tàu khách quốc tế Hạ Long — nguồn tạm lỗi (chưa xác minh phí qua cảng)
  '871a6ee7-1d46-49bb-957a-ff50260b1f3b': {
    placeId: '871a6ee7-1d46-49bb-957a-ff50260b1f3b',
    pricingMode: 'UNVERIFIED',
    isVerifiedPrice: false,
    sourceUrl: null,
    checkedDate: '2026-11-27',
  },
  // Chợ Hạ Long II — chưa xác minh
  '6215446b-2fdd-4014-aacf-23de6e45e264': {
    placeId: '6215446b-2fdd-4014-aacf-23de6e45e264',
    pricingMode: 'UNVERIFIED',
    isVerifiedPrice: false,
    sourceUrl: null,
    checkedDate: '2026-11-27',
  },
  // Cầu Rồng — miễn phí có nguồn cổng Sở Du lịch Đà Nẵng
  '9974ff88-5418-5867-ae49-1b72e0f0861f': {
    placeId: '9974ff88-5418-5867-ae49-1b72e0f0861f',
    pricingMode: 'FREE',
    isVerifiedPrice: true,
    sourceUrl: 'https://danangfantasticity.com/cac-cay-cau/cau-rong',
    checkedDate: '2026-11-27',
  },
  // Bãi biển Mỹ Khê — miễn phí tắm biển có nguồn Báo Chính phủ
  '2f202acf-c2bb-526a-9803-aaca142ffdad': {
    placeId: '2f202acf-c2bb-526a-9803-aaca142ffdad',
    pricingMode: 'FREE',
    isVerifiedPrice: true,
    sourceUrl:
      'https://baochinhphu.vn/gia-thu-tien-dich-vu-tai-cac-khu-nha-tam-nuoc-ngot-ven-bien-10277983.htm',
    checkedDate: '2026-11-27',
  },
  // Danh thắng Ngũ Hành Sơn
  '6f758ad7-5685-57b5-9913-d28e15bdb7c5': {
    placeId: '6f758ad7-5685-57b5-9913-d28e15bdb7c5',
    pricingMode: 'SINGLE_POI',
    isVerifiedPrice: true,
    sourceUrl: 'https://nguhanhson.org/',
    checkedDate: '2026-11-27',
    ticketGroupId: 'DANANG_NGU_HANH_SON_THUY_SON',
    audienceUnitPrices: {
      adult: [40000, 20000, 60000],
      student: [10000, 7000, 17000],
      child: [10000, 7000, 17000],
      infant_free: [0],
    },
  },
  // Bảo tàng Điêu khắc Chăm Đà Nẵng
  'a24d48ff-59d6-5e53-af77-36448e60d1cc': {
    placeId: 'a24d48ff-59d6-5e53-af77-36448e60d1cc',
    pricingMode: 'SINGLE_POI',
    isVerifiedPrice: true,
    sourceUrl: 'https://chammuseum.vn/ve-tham-quan/',
    checkedDate: '2026-11-27',
    audienceUnitPrices: {
      adult: [60000],
      student: [20000],
      resident_danang: [20000],
      child: [0],
      senior: [0],
      infant_free: [0],
    },
  },
  // Chùa Linh Ứng Non Nước — thuộc khu vé Ngọn Thủy Sơn
  '5fc0994a-e578-4a25-b375-7f079e6dc3ba': {
    placeId: '5fc0994a-e578-4a25-b375-7f079e6dc3ba',
    pricingMode: 'AREA_TICKET',
    isVerifiedPrice: true,
    sourceUrl: 'https://nguhanhson.org/',
    checkedDate: '2026-11-27',
    ticketGroupId: 'DANANG_NGU_HANH_SON_THUY_SON',
    audienceUnitPrices: {
      adult: [40000],
      student: [10000],
      child: [10000],
      infant_free: [0],
    },
  },
  // Khu du lịch Bà Nà Hills
  '987f490f-b1c7-42cf-b92e-300d57fd8d5f': {
    placeId: '987f490f-b1c7-42cf-b92e-300d57fd8d5f',
    pricingMode: 'SINGLE_POI',
    isVerifiedPrice: true,
    sourceUrl: 'https://sunworld.vn/operations',
    checkedDate: '2026-11-27',
    audienceUnitPrices: {
      adult: [1000000],
      resident_danang: [650000],
      child: [800000],
      senior: [800000],
      infant_free: [0],
    },
  },
  // Bảo tàng Đà Nẵng
  'cb6cce60-8270-5f43-b9f7-42de2d7d7da3': {
    placeId: 'cb6cce60-8270-5f43-b9f7-42de2d7d7da3',
    pricingMode: 'SINGLE_POI',
    isVerifiedPrice: true,
    sourceUrl:
      'https://baotangdanang.vn/thong-bao-muc-thu-phi-tham-quan-tai-bao-tang-da-nang-va-bao-tang-di-tich-quang-nam/',
    checkedDate: '2026-11-27',
    audienceUnitPrices: {
      adult: [50000],
      student: [20000],
      resident_danang: [20000],
      child: [0],
      senior: [0],
      infant_free: [0],
    },
  },
  // Bến du thuyền Cá Heo — chưa xác minh
  '62a874a9-13e2-44d2-95b5-30e980b98965': {
    placeId: '62a874a9-13e2-44d2-95b5-30e980b98965',
    pricingMode: 'UNVERIFIED',
    isVerifiedPrice: false,
    sourceUrl: null,
    checkedDate: '2026-11-27',
  },
};

export function formatDotVnd(amount: number): string {
  return Math.max(0, Math.trunc(amount))
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

/**
 * Resolves verified pricing provenance rule for a `placeId`.
 * Supports optional override via `placeSources[].rawData._verified_pricing` or
 * `_legacy_no_price_provenance` (so legacy DB rows lacking price provenance fail closed).
 */
export function resolvePlacePricingRule(
  placeId: string | null | undefined,
  placeSources?: ReadonlyArray<PlaceProvenanceSourceRow> | null,
): VerifiedPlacePricingRule | null {
  if (!placeId || typeof placeId !== 'string') return null;
  const trimmedId = placeId.trim();
  if (!trimmedId) return null;

  if (Array.isArray(placeSources)) {
    for (const src of placeSources) {
      const raw = src?.rawData;
      if (raw && typeof raw === 'object') {
        const rec = raw as Record<string, unknown>;
        if (rec._legacy_no_price_provenance === true) {
          return null;
        }
        const custom = rec._verified_pricing;
        if (custom && typeof custom === 'object') {
          const c = custom as Record<string, unknown>;
          const isVerified = c.isVerifiedPrice === true;
          const sourceUrl =
            typeof c.sourceUrl === 'string' && c.sourceUrl.trim().length > 0
              ? c.sourceUrl.trim()
              : null;
          const pricingMode = (c.pricingMode as CuratedPricingMode) || 'UNVERIFIED';
          return {
            placeId: trimmedId,
            pricingMode,
            isVerifiedPrice: isVerified && sourceUrl !== null,
            sourceUrl,
            checkedDate:
              typeof c.checkedDate === 'string' ? c.checkedDate : '2026-11-27',
            audienceUnitPrices: c.audienceUnitPrices as
              | Partial<Record<TravelerAudienceCategory, number[]>>
              | undefined,
            ticketGroupId:
              typeof c.ticketGroupId === 'string' ? c.ticketGroupId : undefined,
          };
        }
      }
    }
  }

  return CURATED_LO1_VERIFIED_PRICING[trimmedId] ?? null;
}

/**
 * Extracts explicit party size and applicable traveler audience from user-supplied context.
 * Never guesses `'adult'` when the text only says generic `"2 người"` or omits audience completely.
 */
export function parseTravelerAudienceContext(params: {
  partySize?: number | null;
  partyDescription?: string | null;
  rawPrompt?: string | null;
}): ParsedAudienceContext {
  const combined = [params.partyDescription ?? '', params.rawPrompt ?? '']
    .join(' ')
    .trim()
    .toLowerCase();

  let detectedSize: number | null =
    typeof params.partySize === 'number' && params.partySize > 0
      ? Math.trunc(params.partySize)
      : null;

  let audience: TravelerAudienceCategory | null = null;

  const audiencePatterns: Array<{
    cat: TravelerAudienceCategory;
    regex: RegExp;
    wordRegexSource: string;
  }> = [
    {
      cat: 'resident_danang',
      regex: /\b(\d{1,2})?\s*(?:người\s+|khách\s+)?thường\s*trú\s*(?:đà\s*nẵng|quảng\s*nam)\b/i,
      wordRegexSource: '(?:người\\s+|khách\\s+)?thường\\s*trú\\s*(?:đà\\s*nẵng|quảng\\s*nam)',
    },
    {
      cat: 'student',
      regex: /\b(\d{1,2})?\s*(?:bạn\s+)?(?:sinh\s*viên|học\s*viên)\b/i,
      wordRegexSource: '(?:bạn\\s+)?(?:sinh\\s*viên|học\\s*viên)',
    },
    {
      cat: 'infant_free',
      regex: /\b(\d{1,2})?\s*trẻ\s*(?:em\s*)?(?:dưới\s*1[.,]2\s*m|<\s*1[.,]2\s*m|dưới\s*6\s*tuổi|<\s*6\s*tuổi)\b/i,
      wordRegexSource: 'trẻ\\s*(?:em\\s*)?(?:dưới\\s*1[.,]2\\s*m|<\\s*1[.,]2\\s*m|dưới\\s*6\\s*tuổi|<\\s*6\\s*tuổi)',
    },
    {
      cat: 'child',
      regex: /\b(\d{1,2})?\s*(?:học\s*sinh|trẻ\s*em)\b/i,
      wordRegexSource: '(?:học\\s*sinh|trẻ\\s*em)',
    },
    {
      cat: 'senior',
      regex: /\b(\d{1,2})?\s*(?:người\s*cao\s*tuổi|cụ\s*già)\b/i,
      wordRegexSource: '(?:người\\s*cao\\s*tuổi|cụ\\s*già)',
    },
    {
      cat: 'adult',
      regex: /\b(\d{1,2})?\s*người\s*lớn\b/i,
      wordRegexSource: 'người\\s*lớn',
    },
  ];

  if (combined.length > 0) {
    for (const entry of audiencePatterns) {
      let matchedWordSize: number | null = null;
      for (const [word, num] of Object.entries(VIET_NUMBER_WORDS)) {
        const wRe = new RegExp(`\\b${word}\\s+${entry.wordRegexSource}\\b`, 'i');
        if (wRe.test(combined)) {
          matchedWordSize = num;
          break;
        }
      }
      const m = combined.match(entry.regex);
      if (matchedWordSize !== null || m) {
        audience = entry.cat;
        if (detectedSize === null) {
          if (m && m[1]) {
            detectedSize = Number(m[1]);
          } else if (matchedWordSize !== null) {
            detectedSize = matchedWordSize;
          } else {
            detectedSize = 1;
          }
        }
        break;
      }
    }
  }

  return {
    partySize: detectedSize ?? 1,
    audience,
    audienceLabelVi: audience ? AUDIENCE_LABELS_VI[audience] : null,
    isAudienceExplicit: audience !== null,
  };
}

/**
 * Classifies a single itinerary item's cost provenance in Preview mode.
 */
export function classifyPreviewItemCostProvenance(params: {
  estimatedCost: number | null;
  resolvedPlaceId: string | null;
  placeSources?: ReadonlyArray<PlaceProvenanceSourceRow> | null;
  audienceContext: ParsedAudienceContext;
  chargedTicketGroupsInDay: Set<string>;
}): ClassifiedCostItemResult {
  const {
    estimatedCost,
    resolvedPlaceId,
    placeSources,
    audienceContext,
    chargedTicketGroupsInDay,
  } = params;

  if (estimatedCost === null || estimatedCost === undefined || !Number.isFinite(estimatedCost)) {
    return {
      costStatus: 'UNKNOWN',
      costBadgeVi: 'Chưa biết giá',
      isVerifiedFree: false,
      costSourceVerified: false,
      verifiedSourceUrl: null,
      provenanceNoteTag: null,
    };
  }

  const normalizedCost = Math.max(0, Math.trunc(estimatedCost));
  if (!resolvedPlaceId) {
    return {
      costStatus: 'ESTIMATED',
      costBadgeVi: 'Tạm tính',
      isVerifiedFree: false,
      costSourceVerified: false,
      verifiedSourceUrl: null,
      provenanceNoteTag: null,
    };
  }

  const rule = resolvePlacePricingRule(resolvedPlaceId, placeSources);
  if (!rule || !rule.isVerifiedPrice || !rule.sourceUrl) {
    return {
      costStatus: 'ESTIMATED',
      costBadgeVi: 'Tạm tính',
      isVerifiedFree: false,
      costSourceVerified: false,
      verifiedSourceUrl: null,
      provenanceNoteTag: null,
    };
  }

  // Case 1: Universal verified FREE admission POI (e.g. Cầu Rồng, Bãi biển Mỹ Khê)
  if (rule.pricingMode === 'FREE') {
    if (normalizedCost === 0) {
      return {
        costStatus: 'VERIFIED',
        costBadgeVi: 'Miễn phí · Đã xác minh',
        isVerifiedFree: true,
        costSourceVerified: true,
        verifiedSourceUrl: rule.sourceUrl,
        provenanceNoteTag: '[Nguồn giá đã xác minh: Miễn phí 0đ]',
      };
    }
    return {
      costStatus: 'ESTIMATED',
      costBadgeVi: 'Tạm tính',
      isVerifiedFree: false,
      costSourceVerified: false,
      verifiedSourceUrl: null,
      provenanceNoteTag: null,
    };
  }

  // Case 2: Tiered paid POI / Route / Area ticket -> requires explicit audience AND exact unitPrice * partySize match
  if (
    !audienceContext.isAudienceExplicit ||
    !audienceContext.audience ||
    !rule.audienceUnitPrices
  ) {
    return {
      costStatus: 'ESTIMATED',
      costBadgeVi: 'Tạm tính',
      isVerifiedFree: false,
      costSourceVerified: false,
      verifiedSourceUrl: null,
      provenanceNoteTag: null,
    };
  }

  const partySize = Math.max(1, audienceContext.partySize);

  // Shared route/area ticket deduplication: if the route/area ticket was already charged earlier today,
  // a second stop on the same route/area is verified ONLY at 0đ (included in shared ticket), never double-charged!
  if (rule.ticketGroupId && chargedTicketGroupsInDay.has(rule.ticketGroupId)) {
    if (normalizedCost === 0) {
      return {
        costStatus: 'VERIFIED',
        costBadgeVi: 'Đã gồm trong vé tuyến · Đã xác minh',
        isVerifiedFree: true,
        costSourceVerified: true,
        verifiedSourceUrl: rule.sourceUrl,
        provenanceNoteTag: `[Nguồn giá đã xác minh: Đã gồm trong vé tuyến ${rule.ticketGroupId} (0đ)]`,
      };
    }
    return {
      costStatus: 'ESTIMATED',
      costBadgeVi: 'Tạm tính',
      isVerifiedFree: false,
      costSourceVerified: false,
      verifiedSourceUrl: null,
      provenanceNoteTag: null,
    };
  }

  const allowedUnits = rule.audienceUnitPrices[audienceContext.audience] ?? [];
  const matchedUnit = allowedUnits.find((u) => u * partySize === normalizedCost);
  if (matchedUnit === undefined) {
    return {
      costStatus: 'ESTIMATED',
      costBadgeVi: 'Tạm tính',
      isVerifiedFree: false,
      costSourceVerified: false,
      verifiedSourceUrl: null,
      provenanceNoteTag: null,
    };
  }

  if (rule.ticketGroupId && normalizedCost > 0) {
    chargedTicketGroupsInDay.add(rule.ticketGroupId);
  }

  const audienceLabel = audienceContext.audienceLabelVi ?? 'khách';
  const tag =
    normalizedCost === 0
      ? `[Nguồn giá đã xác minh: ${partySize} ${audienceLabel} × 0đ (miễn phí)]`
      : `[Nguồn giá đã xác minh: ${partySize} ${audienceLabel} × ${formatDotVnd(matchedUnit)}đ/lượt]`;

  return {
    costStatus: 'VERIFIED',
    costBadgeVi: normalizedCost === 0 ? 'Miễn phí · Đã xác minh' : 'Đã xác minh',
    isVerifiedFree: normalizedCost === 0,
    costSourceVerified: true,
    verifiedSourceUrl: rule.sourceUrl,
    provenanceNoteTag: tag,
  };
}

/**
 * Attaches the verified provenance marker onto `notes` if not already present so saved
 * itineraries can be deterministically re-verified on `GET /trips/:id`, while legacy
 * `itinerary_items` lacking price+audience provenance remain `'ESTIMATED'`.
 */
export function attachVerifiedProvenanceNote(
  existingNotes: string | null | undefined,
  provenanceNoteTag: string | null,
): string | undefined {
  const base = typeof existingNotes === 'string' ? existingNotes.trim() : '';
  if (!provenanceNoteTag) {
    return base.length > 0 ? base : undefined;
  }
  if (VERIFIED_NOTE_MARKER_RE.test(base)) {
    return base;
  }
  return base.length > 0 ? `${base} ${provenanceNoteTag}` : provenanceNoteTag;
}

/**
 * Classifies a persisted `itinerary_items` row when reopening a trip (`GET /trips/:id`).
 * Legacy items without verified price+audience provenance fail closed to `'ESTIMATED'`.
 */
export function classifySavedItemCostProvenance(params: {
  estimatedCost: number | null | undefined;
  placeId: string | null | undefined;
  notes: string | null | undefined;
  placeSources?: ReadonlyArray<PlaceProvenanceSourceRow> | null;
  chargedTicketGroupsInDay: Set<string>;
}): ClassifiedCostItemResult {
  const {
    estimatedCost,
    placeId,
    notes,
    placeSources,
    chargedTicketGroupsInDay,
  } = params;

  if (estimatedCost === null || estimatedCost === undefined || !Number.isFinite(estimatedCost)) {
    return {
      costStatus: 'UNKNOWN',
      costBadgeVi: 'Chưa biết giá',
      isVerifiedFree: false,
      costSourceVerified: false,
      verifiedSourceUrl: null,
      provenanceNoteTag: null,
    };
  }

  const normalizedCost = Math.max(0, Math.trunc(estimatedCost));
  const rule = resolvePlacePricingRule(placeId, placeSources);
  if (!rule || !rule.isVerifiedPrice || !rule.sourceUrl) {
    return {
      costStatus: 'ESTIMATED',
      costBadgeVi: 'Tạm tính',
      isVerifiedFree: false,
      costSourceVerified: false,
      verifiedSourceUrl: null,
      provenanceNoteTag: null,
    };
  }

  // Universal FREE admission with authoritative source (0đ for all audiences)
  if (rule.pricingMode === 'FREE' && normalizedCost === 0) {
    return {
      costStatus: 'VERIFIED',
      costBadgeVi: 'Miễn phí · Đã xác minh',
      isVerifiedFree: true,
      costSourceVerified: true,
      verifiedSourceUrl: rule.sourceUrl,
      provenanceNoteTag: null,
    };
  }

  // Tiered paid POIs on saved items require explicit verified provenance marker AND re-validation
  // against the authoritative rule so legacy itinerary_items lacking provenance stay 'ESTIMATED'.
  const noteStr = typeof notes === 'string' ? notes : '';
  const markerMatch = noteStr.match(VERIFIED_NOTE_MARKER_RE);
  if (!markerMatch) {
    return {
      costStatus: 'ESTIMATED',
      costBadgeVi: 'Tạm tính',
      isVerifiedFree: false,
      costSourceVerified: false,
      verifiedSourceUrl: null,
      provenanceNoteTag: null,
    };
  }

  const markerBody = markerMatch[1];
  if (
    normalizedCost === 0 &&
    rule.ticketGroupId &&
    markerBody.toLowerCase().includes('vé tuyến')
  ) {
    return {
      costStatus: 'VERIFIED',
      costBadgeVi: 'Đã gồm trong vé tuyến · Đã xác minh',
      isVerifiedFree: true,
      costSourceVerified: true,
      verifiedSourceUrl: rule.sourceUrl,
      provenanceNoteTag: null,
    };
  }

  const parsedAudience = parseTravelerAudienceContext({
    partyDescription: markerBody,
  });
  return classifyPreviewItemCostProvenance({
    estimatedCost: normalizedCost,
    resolvedPlaceId: placeId ?? null,
    placeSources,
    audienceContext: parsedAudience,
    chargedTicketGroupsInDay,
  });
}

/**
 * Formats the C4 provenance budget summary line using middle-dot (` · `) separators.
 * Demo output example: `"Đã xác minh 80.000đ · Tạm tính 120.000đ · 1 khoản chưa biết giá"`.
 */
export function formatCostProvenanceSummaryVi(
  breakdown: CostProvenanceBreakdown,
  options?: {
    totalBudget?: number | null;
    isOverBudget?: boolean;
    knownCostTotal?: number;
  },
): string {
  const segments: string[] = [];

  if (breakdown.verifiedPlaceCostItemCount > 0) {
    if (
      breakdown.verifiedPlaceCostTotal === 0 &&
      breakdown.verifiedFreeItemCount > 0
    ) {
      segments.push('Đã xác minh 0đ (miễn phí)');
    } else {
      segments.push(
        `Đã xác minh ${formatDotVnd(breakdown.verifiedPlaceCostTotal)}đ`,
      );
    }
  }

  if (breakdown.unverifiedAiEstimatedItemCount > 0) {
    segments.push(
      `Tạm tính ${formatDotVnd(breakdown.unverifiedAiEstimatedCostTotal)}đ`,
    );
  }

  if (breakdown.unknownCostItemCount > 0) {
    segments.push(`${breakdown.unknownCostItemCount} khoản chưa biết giá`);
  }

  const base =
    segments.length > 0 ? segments.join(' · ') : 'Tạm tính 0đ';

  if (
    options?.isOverBudget &&
    typeof options.totalBudget === 'number' &&
    options.totalBudget > 0 &&
    typeof options.knownCostTotal === 'number' &&
    options.knownCostTotal > options.totalBudget
  ) {
    const over = options.knownCostTotal - options.totalBudget;
    return breakdown.unknownCostItemCount > 0
      ? `${base} (vượt ngân sách ít nhất ${formatDotVnd(over)}đ)`
      : `${base} (vượt ngân sách ${formatDotVnd(over)}đ)`;
  }

  return base;
}
