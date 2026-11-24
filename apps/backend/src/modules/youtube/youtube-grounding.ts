import { BadRequestException, UnauthorizedException } from "@nestjs/common";
import * as crypto from "crypto";
import { YOUTUBE_ERROR_CODES } from "../../common/constants/youtube-error-codes";
import {
  EXPLICIT_TZ_ISO_REGEX,
  YOUTUBE_VIDEO_ID_REGEX,
} from "./dto/youtube-update.dto";

export const MAX_COORDINATE_MATCH_METERS = 250;
export const MAX_CITY_COORDINATE_MATCH_METERS = 50_000;

export interface VerifiedPlaceCandidate {
  id: string;
  destinationId: string;
  name: string;
  nameEn: string | null;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  destinationName: string;
  destinationSlug: string;
  province: string | null;
  provenanceSources: Array<{
    sourceName: string;
    sourceId: string;
    canonicalUrl: string | null;
  }>;
  verifiedAliases: string[];
}

export interface VerifiedDestinationCandidate {
  id: string;
  name: string;
  nameEn: string | null;
  slug: string;
  province: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface NormalizedYoutubeEventInput {
  eventId?: string;
  videoId: string;
  channelId: string;
  channelTitle?: string | null;
  title: string;
  description?: string | null;
  tags: string[];
  publishedAt: Date;
  sourceUpdatedAt?: Date | null;
  latitude?: number | null;
  longitude?: number | null;
  candidatePlaceId?: string | null;
}

export interface GroundingDecision {
  status: "LINKED" | "LINKED_CITY" | "UNLINKED_NO_BASIS";
  scope: "POI" | "CITY" | "NONE";
  placeId: string | null;
  destinationId: string | null;
  groundingBasis: string | null;
  decisionReason: string;
  groundingEvidence: Record<string, unknown>;
}

const KNOWN_VIETNAM_DESTINATION_GROUPS: ReadonlyArray<{
  canonicalSlug: string;
  terms: readonly string[];
}> = [
  {
    canonicalSlug: "ha-long",
    terms: [
      "ha long",
      "quang ninh",
      "hon gai",
      "hong gai",
      "bai chay",
      "tuan chau",
      "bach dang",
    ],
  },
  {
    canonicalSlug: "ha-noi",
    terms: ["ha noi", "hanoi", "hoan kiem", "ba dinh", "tay ho", "dong da"],
  },
  {
    canonicalSlug: "da-nang",
    terms: [
      "da nang",
      "danang",
      "son tra",
      "ngu hanh son",
      "hai chau",
      "ba na",
    ],
  },
  {
    canonicalSlug: "phu-quoc",
    terms: ["phu quoc", "kien giang", "grand world phu quoc"],
  },
  { canonicalSlug: "da-lat", terms: ["da lat", "dalat", "lam dong"] },
  {
    canonicalSlug: "ho-chi-minh",
    terms: ["ho chi minh", "sai gon", "saigon", "ben thanh"],
  },
  { canonicalSlug: "hoi-an", terms: ["hoi an"] },
  {
    canonicalSlug: "hue",
    terms: ["co do hue", "thanh pho hue", "thua thien hue"],
  },
  { canonicalSlug: "nha-trang", terms: ["nha trang", "khanh hoa"] },
  { canonicalSlug: "sa-pa", terms: ["sa pa", "sapa", "lao cai"] },
  { canonicalSlug: "bac-ninh", terms: ["bac ninh"] },
  { canonicalSlug: "hai-phong", terms: ["hai phong", "cat ba"] },
  { canonicalSlug: "vung-tau", terms: ["vung tau", "ba ria"] },
];

const GENERIC_SINGLE_WORD_STOPWORDS = new Set([
  "thap",
  "cot",
  "dong",
  "ho",
  "nha",
  "cau",
  "den",
  "chua",
  "cong",
  "vien",
  "bao",
  "tang",
  "ben",
  "pha",
  "cang",
  "bai",
  "bien",
  "nui",
  "hon",
  "hang",
  "khu",
  "pho",
  "du",
  "lich",
  "park",
  "tower",
  "clock",
  "bridge",
  "beach",
  "cave",
  "island",
  "ferry",
  "terminal",
  "museum",
  "hotel",
  "cruise",
]);

export function foldVietnamese(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[đĐ]/g, "d")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function normalizeSpacedLower(text: string): string {
  return text
    .normalize("NFC")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function containsWholePhrase(
  haystackNorm: string,
  needleNorm: string,
): boolean {
  if (!haystackNorm || !needleNorm) return false;
  return ` ${haystackNorm} `.includes(` ${needleNorm} `);
}

function meaningfulTokens(foldedPhrase: string): string[] {
  return foldedPhrase
    .split(" ")
    .filter(
      (tok) => tok.length >= 2 && !GENERIC_SINGLE_WORD_STOPWORDS.has(tok),
    );
}

export function haversineMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number {
  const r = 6371000;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function computeYoutubeDedupeKey(input: {
  eventId?: string | null;
  videoId: string;
  publishedAt: Date;
  sourceUpdatedAt?: Date | null;
}): string {
  const explicitId = input.eventId?.trim();
  if (explicitId) {
    return `yt:event:${explicitId}`;
  }
  const versionInstant = (
    input.sourceUpdatedAt ?? input.publishedAt
  ).toISOString();
  return `yt:video:${input.videoId}:${versionInstant}`;
}

export function extractVerifiedAliasesFromDescription(
  placeName: string,
  description: string | null | undefined,
): string[] {
  if (!description) return [];
  const aliases = new Set<string>();
  const leadSentence = description.split(/[.!?]/, 1)[0] ?? "";
  // Extract lead alias pattern such as "Cột Đồng Hồ (Tháp Đồng Hồ)" when anchored to the canonical POI name
  const match = leadSentence.match(/^([^,(]{3,60})\s*\(([^)]{3,60})\)/u);
  if (match) {
    const outer = match[1].trim();
    const inner = match[2].trim();
    const foldedCanonical = foldVietnamese(placeName);
    if (
      foldVietnamese(inner) === foldedCanonical &&
      foldVietnamese(outer).split(" ").length >= 2
    ) {
      aliases.add(outer);
    } else if (
      foldVietnamese(outer) === foldedCanonical &&
      foldVietnamese(inner).split(" ").length >= 2
    ) {
      aliases.add(inner);
    }
  }
  return [...aliases];
}

function detectMentionedDestinationSlugs(foldedCorpus: string): string[] {
  const found: string[] = [];
  for (const grp of KNOWN_VIETNAM_DESTINATION_GROUPS) {
    if (grp.terms.some((t) => containsWholePhrase(foldedCorpus, t))) {
      found.push(grp.canonicalSlug);
    }
  }
  return found;
}

function destinationContextTermsForPlace(
  candidate: VerifiedPlaceCandidate,
): string[] {
  const terms = new Set<string>();
  for (const raw of [
    candidate.destinationName,
    candidate.province,
    candidate.address,
  ]) {
    if (raw && raw.trim().length >= 3) {
      terms.add(foldVietnamese(raw));
    }
  }
  const known = KNOWN_VIETNAM_DESTINATION_GROUPS.find(
    (g) => g.canonicalSlug === candidate.destinationSlug,
  );
  if (known) {
    for (const t of known.terms) {
      terms.add(t);
    }
  }
  return [...terms].filter((t) => t.length >= 3);
}

function evaluateDestinationCityFallback(
  event: NormalizedYoutubeEventInput,
  foldedCorpus: string,
  mentionedSlugs: string[],
  hasCoords: boolean,
  verifiedDestinations: VerifiedDestinationCandidate[],
): GroundingDecision | null {
  if (verifiedDestinations.length === 0) {
    return null;
  }

  if (mentionedSlugs.length > 1) {
    return {
      status: "UNLINKED_NO_BASIS",
      scope: "NONE",
      placeId: null,
      destinationId: null,
      groundingBasis: null,
      decisionReason: "conflicting_city_mention",
      groundingEvidence: {
        dataGovernanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
        notPrimaryFactualCorpus: true,
        mentionedDestinations: mentionedSlugs,
        eventCoordinates: hasCoords
          ? { latitude: event.latitude, longitude: event.longitude }
          : null,
      },
    };
  }

  const matchedDestinations: Array<{
    dest: VerifiedDestinationCandidate;
    matchedTerms: string[];
  }> = [];

  for (const dest of verifiedDestinations) {
    const terms = new Set<string>();
    for (const raw of [dest.name, dest.nameEn, dest.province]) {
      if (raw && raw.trim().length >= 3) {
        const folded = foldVietnamese(raw);
        if (folded.length >= 3) {
          terms.add(folded);
        }
      }
    }
    const slugAsWords = foldVietnamese(dest.slug.replace(/-/g, " "));
    if (slugAsWords.length >= 3) {
      terms.add(slugAsWords);
    }
    const known = KNOWN_VIETNAM_DESTINATION_GROUPS.find(
      (g) => g.canonicalSlug === dest.slug,
    );
    if (known) {
      for (const t of known.terms) {
        terms.add(t);
      }
    }

    const matchedTerms = [...terms].filter((t) =>
      containsWholePhrase(foldedCorpus, t),
    );
    const matchesSlug = mentionedSlugs.includes(dest.slug);

    if (matchesSlug || matchedTerms.length > 0) {
      matchedDestinations.push({ dest, matchedTerms });
    }
  }

  if (matchedDestinations.length === 0) {
    return null;
  }

  if (matchedDestinations.length > 1) {
    return {
      status: "UNLINKED_NO_BASIS",
      scope: "NONE",
      placeId: null,
      destinationId: null,
      groundingBasis: null,
      decisionReason: "ambiguous_destination_match",
      groundingEvidence: {
        dataGovernanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
        notPrimaryFactualCorpus: true,
        candidateDestinationIds: matchedDestinations.map((m) => m.dest.id),
        mentionedDestinations: mentionedSlugs,
      },
    };
  }

  const winner = matchedDestinations[0];
  const dest = winner.dest;

  if (mentionedSlugs.some((s) => s !== dest.slug)) {
    return {
      status: "UNLINKED_NO_BASIS",
      scope: "NONE",
      placeId: null,
      destinationId: null,
      groundingBasis: null,
      decisionReason: "conflicting_city_mention",
      groundingEvidence: {
        dataGovernanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
        notPrimaryFactualCorpus: true,
        candidateDestinationId: dest.id,
        mentionedDestinations: mentionedSlugs,
      },
    };
  }

  let distanceMeters: number | null = null;
  if (hasCoords && dest.latitude !== null && dest.longitude !== null) {
    distanceMeters =
      Math.round(
        haversineMeters(
          event.latitude as number,
          event.longitude as number,
          dest.latitude,
          dest.longitude,
        ) * 10,
      ) / 10;
    if (distanceMeters > MAX_CITY_COORDINATE_MATCH_METERS) {
      return {
        status: "UNLINKED_NO_BASIS",
        scope: "NONE",
        placeId: null,
        destinationId: null,
        groundingBasis: null,
        decisionReason: "coordinate_conflict_with_destination",
        groundingEvidence: {
          dataGovernanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
          notPrimaryFactualCorpus: true,
          candidateDestinationId: dest.id,
          candidateDestinationSlug: dest.slug,
          distanceMeters,
          maxAllowedMeters: MAX_CITY_COORDINATE_MATCH_METERS,
          mentionedDestinations: mentionedSlugs,
          eventCoordinates: {
            latitude: event.latitude,
            longitude: event.longitude,
          },
        },
      };
    }
  }

  return {
    status: "LINKED_CITY",
    scope: "CITY",
    placeId: null,
    destinationId: dest.id,
    groundingBasis: "UNIQUE_DESTINATION_CONTEXT_FALLBACK",
    decisionReason: "verified_destination_city_fallback_passed",
    groundingEvidence: {
      dataGovernanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
      notPrimaryFactualCorpus: true,
      matchedDestinationId: dest.id,
      matchedDestinationName: dest.name,
      destinationSlug: dest.slug,
      matchedContextTerms: winner.matchedTerms,
      mentionedDestinations: mentionedSlugs,
      distanceMeters,
    },
  };
}

export function evaluatePoiGrounding(
  event: NormalizedYoutubeEventInput,
  verifiedCandidates: VerifiedPlaceCandidate[],
  verifiedDestinations: VerifiedDestinationCandidate[] = [],
): GroundingDecision {
  const rawCorpus = [event.title, event.description ?? "", ...event.tags]
    .filter(Boolean)
    .join(" \n ");
  const accentedCorpus = normalizeSpacedLower(rawCorpus);
  const foldedCorpus = foldVietnamese(rawCorpus);
  const rawLowerCorpus = rawCorpus.toLowerCase();

  const hasCoords =
    typeof event.latitude === "number" && typeof event.longitude === "number";
  const mentionedSlugs = detectMentionedDestinationSlugs(foldedCorpus);

  if (event.candidatePlaceId) {
    const targetExists = verifiedCandidates.some(
      (c) => c.id === event.candidatePlaceId,
    );
    if (!targetExists) {
      return {
        status: "UNLINKED_NO_BASIS",
        scope: "NONE",
        placeId: null,
        destinationId: null,
        groundingBasis: null,
        decisionReason: "target_place_unverified_or_missing",
        groundingEvidence: {
          dataGovernanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
          notPrimaryFactualCorpus: true,
          requestedCandidatePlaceId: event.candidatePlaceId,
        },
      };
    }
  }

  if (verifiedCandidates.length === 0) {
    const cityFallback = evaluateDestinationCityFallback(
      event,
      foldedCorpus,
      mentionedSlugs,
      hasCoords,
      verifiedDestinations,
    );
    if (cityFallback) {
      return cityFallback;
    }
    return {
      status: "UNLINKED_NO_BASIS",
      scope: "NONE",
      placeId: null,
      destinationId: null,
      groundingBasis: null,
      decisionReason: "no_verified_poi_candidates",
      groundingEvidence: {
        dataGovernanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
        notPrimaryFactualCorpus: true,
        videoId: event.videoId,
      },
    };
  }

  interface ScoredMatch {
    candidate: VerifiedPlaceCandidate;
    basis: string;
    tier: number;
    distanceMeters: number | null;
    matchedPhrases: string[];
    matchedContextTerms: string[];
    matchedSourceUrls: string[];
  }

  const passing: ScoredMatch[] = [];
  let sawCoordConflict = false;
  let sawCityConflict = false;
  let sawNameOnlyWithoutContext = false;

  for (const cand of verifiedCandidates) {
    if (event.candidatePlaceId && cand.id !== event.candidatePlaceId) {
      continue;
    }

    let distanceMeters: number | null = null;
    if (hasCoords && cand.latitude !== null && cand.longitude !== null) {
      distanceMeters =
        Math.round(
          haversineMeters(
            event.latitude as number,
            event.longitude as number,
            cand.latitude,
            cand.longitude,
          ) * 10,
        ) / 10;
    }

    // Phrase matching against canonical name, English name, and verified aliases
    const candidatePhrases = [
      cand.name,
      ...(cand.nameEn ? [cand.nameEn] : []),
      ...cand.verifiedAliases,
    ].filter((p) => p && p.trim().length >= 3);

    const matchedPhrases: string[] = [];
    for (const phrase of candidatePhrases) {
      const accNeedle = normalizeSpacedLower(phrase);
      const foldNeedle = foldVietnamese(phrase);
      const tokenCount = foldNeedle.split(" ").filter(Boolean).length;
      const nonStopTokens = meaningfulTokens(foldNeedle);

      // Require >= 2 words (or >= 1 non-generic distinctive token of length >= 5)
      if (tokenCount < 2 && nonStopTokens.every((t) => t.length < 5)) {
        continue;
      }
      if (
        containsWholePhrase(accentedCorpus, accNeedle) ||
        containsWholePhrase(foldedCorpus, foldNeedle)
      ) {
        matchedPhrases.push(phrase);
      }
    }

    const matchedSourceUrls = cand.provenanceSources
      .map((s) => s.canonicalUrl)
      .filter((u): u is string =>
        Boolean(u && rawLowerCorpus.includes(u.toLowerCase())),
      );

    const explicitPoiRef =
      event.candidatePlaceId === cand.id || matchedSourceUrls.length > 0;

    if (matchedPhrases.length === 0 && !explicitPoiRef) {
      continue;
    }

    // Gate 1: Coordinate contradiction fails closed immediately
    if (
      distanceMeters !== null &&
      distanceMeters > MAX_COORDINATE_MATCH_METERS
    ) {
      sawCoordConflict = true;
      continue;
    }

    // Gate 2: Conflicting destination mention fails closed
    const contextTerms = destinationContextTermsForPlace(cand);
    const matchedContextTerms = contextTerms.filter((t) =>
      containsWholePhrase(foldedCorpus, t),
    );
    const mentionsOwnSlug =
      mentionedSlugs.includes(cand.destinationSlug) ||
      matchedContextTerms.length > 0;
    const mentionsForeignSlug = mentionedSlugs.some(
      (s) => s !== cand.destinationSlug,
    );
    if (mentionsForeignSlug && !mentionsOwnSlug) {
      sawCityConflict = true;
      continue;
    }

    // Gate 3: Positive corroboration basis required
    const withinCoordRadius =
      distanceMeters !== null && distanceMeters <= MAX_COORDINATE_MATCH_METERS;

    if (matchedPhrases.length > 0 && withinCoordRadius) {
      passing.push({
        candidate: cand,
        basis: "NAME_AND_COORDINATE_CORROBORATION",
        tier: 3,
        distanceMeters,
        matchedPhrases,
        matchedContextTerms,
        matchedSourceUrls,
      });
    } else if (
      explicitPoiRef &&
      (matchedPhrases.length > 0 || withinCoordRadius)
    ) {
      passing.push({
        candidate: cand,
        basis: "EXPLICIT_POI_REF_AND_TEXT_MATCH",
        tier: 2,
        distanceMeters,
        matchedPhrases,
        matchedContextTerms,
        matchedSourceUrls,
      });
    } else if (
      matchedPhrases.length > 0 &&
      matchedContextTerms.length > 0 &&
      !mentionsForeignSlug
    ) {
      passing.push({
        candidate: cand,
        basis: "UNIQUE_NAME_AND_DESTINATION_CONTEXT",
        tier: 1,
        distanceMeters,
        matchedPhrases,
        matchedContextTerms,
        matchedSourceUrls,
      });
    } else {
      sawNameOnlyWithoutContext = true;
    }
  }

  if (passing.length === 0) {
    if (
      !sawCoordConflict &&
      !sawCityConflict &&
      !sawNameOnlyWithoutContext &&
      !event.candidatePlaceId
    ) {
      const cityFallback = evaluateDestinationCityFallback(
        event,
        foldedCorpus,
        mentionedSlugs,
        hasCoords,
        verifiedDestinations,
      );
      if (cityFallback) {
        return cityFallback;
      }
    }

    let reason = "no_poi_name_or_coordinate_match";
    if (sawCoordConflict) {
      reason = "coordinate_conflict_with_poi";
    } else if (sawCityConflict) {
      reason = "conflicting_city_mention";
    } else if (sawNameOnlyWithoutContext) {
      reason = "missing_destination_or_spatial_corroboration";
    }
    return {
      status: "UNLINKED_NO_BASIS",
      scope: "NONE",
      placeId: null,
      destinationId: null,
      groundingBasis: null,
      decisionReason: reason,
      groundingEvidence: {
        dataGovernanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
        notPrimaryFactualCorpus: true,
        mentionedDestinations: mentionedSlugs,
        eventCoordinates: hasCoords
          ? { latitude: event.latitude, longitude: event.longitude }
          : null,
      },
    };
  }

  passing.sort((a, b) => {
    if (b.tier !== a.tier) return b.tier - a.tier;
    if (a.distanceMeters !== null && b.distanceMeters !== null) {
      return a.distanceMeters - b.distanceMeters;
    }
    return b.matchedPhrases.length - a.matchedPhrases.length;
  });

  if (passing.length > 1) {
    const top = passing[0];
    const second = passing[1];
    const tiedTier = top.tier === second.tier;
    const tiedDistance =
      top.distanceMeters === null ||
      second.distanceMeters === null ||
      Math.abs(top.distanceMeters - second.distanceMeters) < 25;
    if (tiedTier && tiedDistance) {
      return {
        status: "UNLINKED_NO_BASIS",
        scope: "NONE",
        placeId: null,
        destinationId: null,
        groundingBasis: null,
        decisionReason: "ambiguous_multiple_poi_candidates",
        groundingEvidence: {
          dataGovernanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
          notPrimaryFactualCorpus: true,
          candidatePlaceIds: passing.map((p) => p.candidate.id),
        },
      };
    }
  }

  const winner = passing[0];
  return {
    status: "LINKED",
    scope: "POI",
    placeId: winner.candidate.id,
    destinationId: winner.candidate.destinationId,
    groundingBasis: winner.basis,
    decisionReason: "verified_poi_grounding_passed",
    groundingEvidence: {
      dataGovernanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
      notPrimaryFactualCorpus: true,
      matchedPlaceId: winner.candidate.id,
      matchedPlaceName: winner.candidate.name,
      destinationId: winner.candidate.destinationId,
      destinationSlug: winner.candidate.destinationSlug,
      matchedPhrases: winner.matchedPhrases,
      matchedContextTerms: winner.matchedContextTerms,
      matchedSourceUrls: winner.matchedSourceUrls,
      distanceMeters: winner.distanceMeters,
      provenanceSources: winner.candidate.provenanceSources.map(
        (s) => `${s.sourceName}:${s.sourceId}`,
      ),
    },
  };
}

function decodeXmlEntities(raw: string): string {
  return raw
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#39;/g, "'")
    .trim();
}

function extractXmlTag(block: string, tagPattern: string): string | null {
  const re = new RegExp(
    `<${tagPattern}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tagPattern}>`,
    "i",
  );
  const m = block.match(re);
  return m ? decodeXmlEntities(m[1]) : null;
}

export function verifyWebSubSignature(
  rawBody: string,
  signatureHeader: string | undefined,
  secret: string | undefined,
): void {
  const trimmedSecret = secret?.trim();
  if (!trimmedSecret) {
    return;
  }
  if (!signatureHeader || !signatureHeader.includes("=")) {
    throw new UnauthorizedException({
      message: "Missing or malformed X-Hub-Signature header",
      errorCode: YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
    });
  }
  const [algoRaw, providedHex] = signatureHeader.trim().split("=", 2);
  const algo = algoRaw.toLowerCase();
  if (algo !== "sha1" && algo !== "sha256") {
    throw new UnauthorizedException({
      message: `Unsupported WebSub signature algorithm: ${algo}`,
      errorCode: YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
    });
  }
  const expectedHex = crypto
    .createHmac(algo, trimmedSecret)
    .update(rawBody, "utf8")
    .digest("hex");
  const a = Buffer.from(expectedHex, "utf8");
  const b = Buffer.from(providedHex.toLowerCase(), "utf8");
  if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
    throw new UnauthorizedException({
      message: "Invalid WebSub X-Hub-Signature digest",
      errorCode: YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
    });
  }
}

export function parseYoutubeAtomFeed(
  xml: string,
): NormalizedYoutubeEventInput[] {
  if (!xml || typeof xml !== "string" || !xml.trim()) {
    throw new BadRequestException("Empty YouTube Atom XML payload");
  }
  if (/<!DOCTYPE|<!ENTITY/i.test(xml)) {
    throw new BadRequestException(
      "XML DOCTYPE/ENTITY declarations are forbidden",
    );
  }
  if (!/<feed[\s>]/i.test(xml)) {
    throw new BadRequestException(
      "Payload is not a valid Atom <feed> document",
    );
  }

  const entries: NormalizedYoutubeEventInput[] = [];
  const entryRegex = /<entry(?:\s[^>]*)?>([\s\S]*?)<\/entry>/gi;
  let match: RegExpExecArray | null;
  while ((match = entryRegex.exec(xml)) !== null) {
    const block = match[1];
    const videoId = extractXmlTag(block, "yt:videoId");
    const channelId = extractXmlTag(block, "yt:channelId");
    const title = extractXmlTag(block, "title");
    const publishedRaw = extractXmlTag(block, "published");
    const updatedRaw = extractXmlTag(block, "updated");
    const authorBlock = extractXmlTag(block, "author") ?? "";
    const channelTitle = extractXmlTag(authorBlock, "name");
    const description =
      extractXmlTag(block, "media:description") ??
      extractXmlTag(block, "summary");
    const geoPoint = extractXmlTag(block, "georss:point");

    if (!videoId || !YOUTUBE_VIDEO_ID_REGEX.test(videoId)) {
      throw new BadRequestException(
        "Atom <entry> missing valid 11-char <yt:videoId>",
      );
    }
    if (!channelId) {
      throw new BadRequestException(
        `Atom <entry> for ${videoId} missing <yt:channelId>`,
      );
    }
    if (!title) {
      throw new BadRequestException(
        `Atom <entry> for ${videoId} missing <title>`,
      );
    }
    if (!publishedRaw || !EXPLICIT_TZ_ISO_REGEX.test(publishedRaw)) {
      throw new BadRequestException(
        `Atom <entry> for ${videoId} missing timezone-qualified <published> timestamp`,
      );
    }
    const publishedAt = new Date(publishedRaw);
    if (Number.isNaN(publishedAt.getTime())) {
      throw new BadRequestException(
        `Invalid <published> timestamp on ${videoId}`,
      );
    }

    let sourceUpdatedAt: Date | null = null;
    if (updatedRaw) {
      if (!EXPLICIT_TZ_ISO_REGEX.test(updatedRaw)) {
        throw new BadRequestException(
          `Atom <entry> for ${videoId} has <updated> without timezone offset`,
        );
      }
      const parsedUpd = new Date(updatedRaw);
      if (Number.isNaN(parsedUpd.getTime())) {
        throw new BadRequestException(
          `Invalid <updated> timestamp on ${videoId}`,
        );
      }
      sourceUpdatedAt = parsedUpd;
    }

    let latitude: number | null = null;
    let longitude: number | null = null;
    if (geoPoint) {
      const parts = geoPoint.trim().split(/\s+/);
      if (parts.length === 2) {
        const lat = Number(parts[0]);
        const lon = Number(parts[1]);
        if (
          Number.isFinite(lat) &&
          Number.isFinite(lon) &&
          lat >= -90 &&
          lat <= 90 &&
          lon >= -180 &&
          lon <= 180
        ) {
          latitude = lat;
          longitude = lon;
        }
      }
    }

    entries.push({
      videoId,
      channelId,
      channelTitle,
      title,
      description,
      tags: [],
      publishedAt,
      sourceUpdatedAt,
      latitude,
      longitude,
    });
  }

  return entries;
}
