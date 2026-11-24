import crypto from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';

const FIXTURE_PATH = new URL('../fixtures/halong_thap_dong_ho.json', import.meta.url);
const HALONG_FIXTURE = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf8'));

const KNOWN_VIETNAM_DESTINATION_GROUPS = [
  {
    canonicalSlug: 'ha-long',
    terms: ['ha long', 'quang ninh', 'hon gai', 'hong gai', 'bai chay', 'tuan chau', 'bach dang'],
  },
  { canonicalSlug: 'ha-noi', terms: ['ha noi', 'hanoi', 'hoan kiem', 'ba dinh'] },
  { canonicalSlug: 'da-nang', terms: ['da nang', 'danang', 'son tra', 'ba na', 'cau rong'] },
  { canonicalSlug: 'phu-quoc', terms: ['phu quoc', 'kien giang', 'grand world phu quoc'] },
  { canonicalSlug: 'da-lat', terms: ['da lat', 'dalat', 'lam dong'] },
  { canonicalSlug: 'ho-chi-minh', terms: ['ho chi minh', 'sai gon', 'saigon', 'ben thanh'] },
  { canonicalSlug: 'hoi-an', terms: ['hoi an'] },
];

const GENERIC_STOPWORDS = new Set([
  'thap', 'cot', 'dong', 'ho', 'nha', 'cau', 'den', 'chua', 'cong', 'vien',
  'bao', 'tang', 'ben', 'pha', 'cang', 'bai', 'bien', 'nui', 'hon', 'hang',
  'khu', 'pho', 'du', 'lich', 'park', 'tower', 'clock', 'bridge', 'beach',
]);

const EXPLICIT_TZ_ISO_RE =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;
const YOUTUBE_VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function foldVietnamese(text) {
  return String(text || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[đĐ]/g, 'd')
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function containsWholePhrase(haystack, needle) {
  if (!haystack || !needle) return false;
  return ` ${haystack} `.includes(` ${needle} `);
}

function haversineMeters(lat1, lon1, lat2, lon2) {
  const r = 6371000;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function decodeXmlEntities(raw) {
  return raw
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&#39;/g, "'")
    .trim();
}

function extractXmlTag(block, tagPattern) {
  const re = new RegExp(`<${tagPattern}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${tagPattern}>`, 'i');
  const m = block.match(re);
  return m ? decodeXmlEntities(m[1]) : null;
}

function parseAtomFeed(xml) {
  if (!xml || !xml.trim()) {
    return { error: { status: 400, message: 'Empty YouTube Atom XML payload' } };
  }
  if (/<!DOCTYPE|<!ENTITY/i.test(xml)) {
    return { error: { status: 400, message: 'XML DOCTYPE/ENTITY declarations are forbidden' } };
  }
  if (!/<feed[\s>]/i.test(xml)) {
    return { error: { status: 400, message: 'Payload is not a valid Atom <feed> document' } };
  }
  const entries = [];
  const entryRe = /<entry(?:\s[^>]*)?>([\s\S]*?)<\/entry>/gi;
  let match;
  while ((match = entryRe.exec(xml)) !== null) {
    const block = match[1];
    const videoId = extractXmlTag(block, 'yt:videoId');
    const channelId = extractXmlTag(block, 'yt:channelId');
    const title = extractXmlTag(block, 'title');
    const publishedRaw = extractXmlTag(block, 'published');
    const updatedRaw = extractXmlTag(block, 'updated');
    const authorBlock = extractXmlTag(block, 'author') || '';
    const channelTitle = extractXmlTag(authorBlock, 'name');
    const description =
      extractXmlTag(block, 'media:description') || extractXmlTag(block, 'summary');
    const geoPoint = extractXmlTag(block, 'georss:point');

    if (!videoId || !YOUTUBE_VIDEO_ID_RE.test(videoId)) {
      return { error: { status: 400, message: 'Atom <entry> missing valid 11-char <yt:videoId>' } };
    }
    if (!channelId) {
      return { error: { status: 400, message: 'Atom <entry> missing <yt:channelId>' } };
    }
    if (!title) {
      return { error: { status: 400, message: 'Atom <entry> missing <title>' } };
    }
    if (!publishedRaw || !EXPLICIT_TZ_ISO_RE.test(publishedRaw) || Number.isNaN(Date.parse(publishedRaw))) {
      return {
        error: { status: 400, message: 'Atom <entry> missing timezone-qualified <published>' },
      };
    }
    let sourceUpdatedAt = null;
    if (updatedRaw) {
      if (!EXPLICIT_TZ_ISO_RE.test(updatedRaw) || Number.isNaN(Date.parse(updatedRaw))) {
        return { error: { status: 400, message: 'Atom <entry> has invalid <updated>' } };
      }
      sourceUpdatedAt = new Date(updatedRaw);
    }
    let latitude = null;
    let longitude = null;
    if (geoPoint) {
      const parts = geoPoint.trim().split(/\s+/);
      if (parts.length === 2) {
        const lat = Number(parts[0]);
        const lon = Number(parts[1]);
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
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
      publishedAt: new Date(publishedRaw),
      sourceUpdatedAt,
      latitude,
      longitude,
    });
  }
  return { entries };
}

function sha256Hex(value) {
  return crypto.createHash('sha256').update(String(value), 'utf8').digest('hex');
}

function b64Url(input) {
  return Buffer.from(input).toString('base64url');
}

export async function startMockServer({
  youtubeSecret = 'e2e-youtube-internal-secret',
  websubSecret = 'e2e-websub-hmac-secret',
  verifyToken = '',
} = {}) {
  const jwtSecret = crypto.randomBytes(24).toString('hex');

  function signJwt(payload, expiresInSeconds) {
    const now = Math.floor(Date.now() / 1000);
    const header = b64Url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const body = b64Url(
      JSON.stringify({
        ...payload,
        iat: now,
        exp: now + expiresInSeconds,
      }),
    );
    const sig = crypto
      .createHmac('sha256', jwtSecret)
      .update(`${header}.${body}`)
      .digest('base64url');
    return `${header}.${body}.${sig}`;
  }

  function verifyJwt(token) {
    if (!token || typeof token !== 'string') return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const expectedSig = crypto
      .createHmac('sha256', jwtSecret)
      .update(`${parts[0]}.${parts[1]}`)
      .digest('base64url');
    if (parts[2] !== expectedSig) return null;
    try {
      const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'));
      if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
        return null;
      }
      return payload;
    } catch {
      return null;
    }
  }

  const state = createInitialState();

  function createInitialState() {
    const destMap = new Map();
    for (const d of Object.values(HALONG_FIXTURE.destinations)) {
      destMap.set(d.id, { ...d });
    }

    const places = new Map();
    const placeSources = [];
    const documents = [
      { id: 'doc-1', placeId: HALONG_FIXTURE.poi.id, source: 'wikipedia', title: 'Hạ Long (thành phố)' },
      { id: 'doc-2', placeId: HALONG_FIXTURE.poi.id, source: 'osm', title: 'Tháp Đồng Hồ OSM' },
    ];

    // Seed 22 verified Ha Long places BEFORE Thap Dong Ho so Thap Dong Ho falls on page 2 when limit=20 (T2-F2-01)
    for (let i = 1; i <= 22; i++) {
      const id = `10000000-0000-4000-8000-${String(i).padStart(12, '0')}`;
      const p = {
        id,
        name: `Điểm tham quan Hạ Long #${String(i).padStart(2, '0')}`,
        nameEn: `Ha Long Point ${i}`,
        aliases: [],
        category: i % 2 === 0 ? 'attraction' : 'viewpoint',
        destinationId: HALONG_FIXTURE.destinations.haLong.id,
        destination: HALONG_FIXTURE.destinations.haLong,
        latitude: 20.95 + i * 0.001,
        longitude: 107.08 + i * 0.001,
        address: `Đường Hạ Long ${i}, Quảng Ninh`,
        openingHours: '08:00 - 21:00',
        rating: 4.3,
        description: `Địa điểm xác minh số ${i} tại Hạ Long.`,
        isVerified: true,
        source: { provider: 'osm', sourceId: `node/${1000 + i}` },
        enrichmentMeta: { verificationStatus: 'verified_osm' },
        placeSources: [
          {
            id: `ps-hl-${i}`,
            placeId: id,
            sourceName: 'osm',
            sourceId: `node/${1000 + i}`,
            canonicalUrl: `https://www.openstreetmap.org/node/${1000 + i}`,
          },
        ],
      };
      places.set(id, p);
      placeSources.push(...p.placeSources);
    }

    // Verified unrated POI with null address/openingHours/rating (T2-F2-03)
    const unratedId = HALONG_FIXTURE.negativeFixtures.unratedVerifiedPlaceId;
    const unratedPlace = {
      id: unratedId,
      name: 'Bến Đoan Hạ Long',
      nameEn: 'Ben Doan Pier',
      aliases: [],
      category: 'attraction',
      destinationId: HALONG_FIXTURE.destinations.haLong.id,
      destination: HALONG_FIXTURE.destinations.haLong,
      latitude: 20.9462,
      longitude: 107.0715,
      address: null,
      openingHours: null,
      rating: null,
      description: null,
      isVerified: true,
      source: { provider: 'osm', sourceId: 'way/111222333' },
      enrichmentMeta: { verificationStatus: 'verified_osm' },
      placeSources: [
        {
          id: 'ps-unrated-1',
          placeId: unratedId,
          sourceName: 'osm',
          sourceId: 'way/111222333',
          canonicalUrl: 'https://www.openstreetmap.org/way/111222333',
        },
      ],
    };
    places.set(unratedId, unratedPlace);
    placeSources.push(...unratedPlace.placeSources);

    // Canonical Thap Dong Ho (page 2 when limit=20)
    const thap = {
      id: HALONG_FIXTURE.poi.id,
      name: HALONG_FIXTURE.poi.name,
      nameEn: HALONG_FIXTURE.poi.nameEn,
      aliases: HALONG_FIXTURE.poi.aliases,
      category: HALONG_FIXTURE.poi.category,
      destinationId: HALONG_FIXTURE.destinations.haLong.id,
      destination: HALONG_FIXTURE.destinations.haLong,
      latitude: HALONG_FIXTURE.poi.latitude,
      longitude: HALONG_FIXTURE.poi.longitude,
      address: 'Vòng xuyến Lê Thánh Tông - 25 Tháng 4, Bạch Đằng, Hạ Long',
      openingHours: null,
      rating: 4.6,
      description: HALONG_FIXTURE.poi.description,
      descriptionSourceUrl: HALONG_FIXTURE.poi.descriptionSourceUrl,
      descriptionLicense: HALONG_FIXTURE.poi.descriptionLicense,
      coverImage: HALONG_FIXTURE.poi.coverImage,
      images: [HALONG_FIXTURE.poi.coverImage],
      isVerified: true,
      source: {
        provider: 'osm',
        sourceId: HALONG_FIXTURE.poi.osmSourceId,
        url: HALONG_FIXTURE.poi.osmUrl,
      },
      enrichmentMeta: {
        verificationStatus: 'verified_media_and_article',
        descriptionSourceUrl: HALONG_FIXTURE.poi.descriptionSourceUrl,
        descriptionLicense: HALONG_FIXTURE.poi.descriptionLicense,
        imageLicense: HALONG_FIXTURE.poi.imageLicense,
        imageAuthor: HALONG_FIXTURE.poi.imageAuthor,
      },
      placeSources: [
        {
          id: 'ps-thap-osm',
          placeId: HALONG_FIXTURE.poi.id,
          sourceName: 'osm',
          sourceId: HALONG_FIXTURE.poi.osmSourceId,
          canonicalUrl: HALONG_FIXTURE.poi.osmUrl,
        },
      ],
    };
    places.set(thap.id, thap);
    placeSources.push(...thap.placeSources);

    // Unverified legacy place (0 placeSources -> 404 on GET, UNLINKED_NO_BASIS on YouTube)
    const unverifiedId = HALONG_FIXTURE.negativeFixtures.unverifiedPlaceId;
    places.set(unverifiedId, {
      id: unverifiedId,
      name: 'Địa Điểm Chưa Xác Minh',
      nameEn: 'Unverified Place',
      aliases: [],
      category: 'attraction',
      destinationId: HALONG_FIXTURE.destinations.haLong.id,
      destination: HALONG_FIXTURE.destinations.haLong,
      latitude: 20.955,
      longitude: 107.09,
      address: null,
      openingHours: null,
      rating: null,
      description: null,
      isVerified: false,
      source: null,
      enrichmentMeta: null,
      placeSources: [],
    });

    return {
      usersById: new Map(),
      usersByEmail: new Map(),
      oauthLinks: new Map(), // `${provider}:${providerUserId}` -> userId
      resetTokensByHash: new Map(), // hash -> { id, userId, expiresAtMs, usedAtMs }
      mailOutbox: [],
      trips: new Map(),
      youtubeUpdatesByDedupeKey: new Map(),
      destinations: destMap,
      places,
      placeSources,
      documents,
    };
  }

  function sendJson(res, statusCode, payload) {
    const body = JSON.stringify(payload);
    res.writeHead(statusCode, {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Length': Buffer.byteLength(body),
    });
    res.end(body);
  }

  function sendSuccess(res, statusCode, data) {
    return sendJson(res, statusCode, {
      success: true,
      data,
      timestamp: new Date().toISOString(),
    });
  }

  function sendError(res, statusCode, errorCode, message, reqPath) {
    return sendJson(res, statusCode, {
      success: false,
      statusCode,
      errorCode,
      message,
      timestamp: new Date().toISOString(),
      path: reqPath,
    });
  }

  function issueTokensForUser(user) {
    const accessToken = signJwt({ sub: user.id, email: user.email, type: 'access' }, 900);
    const refreshToken = signJwt({ sub: user.id, email: user.email, type: 'refresh' }, 604800);
    return { access_token: accessToken, refresh_token: refreshToken };
  }

  function sanitizeUser(user) {
    return {
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
      isVerified: user.isVerified,
      providers: [...user.providers],
    };
  }

  function getAuthUser(req) {
    const auth = req.headers.authorization;
    if (!auth || !auth.startsWith('Bearer ')) return null;
    const payload = verifyJwt(auth.slice(7).trim());
    if (!payload || payload.type !== 'access') return null;
    return state.usersById.get(payload.sub) || null;
  }

  function evaluateGrounding(event) {
    const verifiedPlaces = [...state.places.values()].filter((p) => p.placeSources.length > 0);
    const rawCorpus = [event.title, event.description || '', ...(event.tags || [])].join(' \n ');
    const foldedCorpus = foldVietnamese(rawCorpus);
    const lowerCorpus = rawCorpus.toLowerCase();
    const hasCoords = typeof event.latitude === 'number' && typeof event.longitude === 'number';

    if (event.candidatePlaceId) {
      const target = verifiedPlaces.find((p) => p.id === event.candidatePlaceId);
      if (!target) {
        return {
          status: 'UNLINKED_NO_BASIS',
          scope: 'NONE',
          placeId: null,
          destinationId: null,
          groundingBasis: null,
          decisionReason: 'target_place_unverified_or_missing',
          groundingEvidence: {
            dataGovernanceRole: 'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
            notPrimaryFactualCorpus: true,
            requestedCandidatePlaceId: event.candidatePlaceId,
          },
        };
      }
    }

    const mentionedSlugs = KNOWN_VIETNAM_DESTINATION_GROUPS.filter((g) =>
      g.terms.some((t) => containsWholePhrase(foldedCorpus, t)),
    ).map((g) => g.canonicalSlug);

    let sawCoordConflict = false;
    let sawCityConflict = false;
    let sawNameOnly = false;
    const passing = [];

    for (const cand of verifiedPlaces) {
      if (event.candidatePlaceId && cand.id !== event.candidatePlaceId) continue;

      let distanceMeters = null;
      if (hasCoords && cand.latitude !== null && cand.longitude !== null) {
        distanceMeters =
          Math.round(haversineMeters(event.latitude, event.longitude, cand.latitude, cand.longitude) * 10) /
          10;
      }

      const phrases = [cand.name, ...(cand.nameEn ? [cand.nameEn] : []), ...(cand.aliases || [])];
      const matchedPhrases = phrases.filter((phrase) => {
        const folded = foldVietnamese(phrase);
        const tokens = folded.split(' ').filter(Boolean);
        const meaningful = tokens.filter((t) => t.length >= 2 && !GENERIC_STOPWORDS.has(t));
        if (tokens.length < 2 && meaningful.every((t) => t.length < 5)) return false;
        return containsWholePhrase(foldedCorpus, folded);
      });

      const matchedUrls = cand.placeSources
        .map((s) => s.canonicalUrl)
        .filter((u) => u && lowerCorpus.includes(u.toLowerCase()));
      const explicitRef = event.candidatePlaceId === cand.id || matchedUrls.length > 0;

      if (matchedPhrases.length === 0 && !explicitRef) continue;

      if (distanceMeters !== null && distanceMeters > 250) {
        sawCoordConflict = true;
        continue;
      }

      const ownGroup = KNOWN_VIETNAM_DESTINATION_GROUPS.find(
        (g) => g.canonicalSlug === cand.destination.slug,
      );
      const contextTerms = [
        foldVietnamese(cand.destination.name),
        foldVietnamese(cand.destination.province),
        ...(ownGroup ? ownGroup.terms : []),
      ].filter(Boolean);

      const matchedContextTerms = contextTerms.filter((t) => containsWholePhrase(foldedCorpus, t));
      const mentionsOwn =
        mentionedSlugs.includes(cand.destination.slug) || matchedContextTerms.length > 0;
      const mentionsForeign = mentionedSlugs.some((s) => s !== cand.destination.slug);

      if (mentionsForeign && !mentionsOwn) {
        sawCityConflict = true;
        continue;
      }

      const withinRadius = distanceMeters !== null && distanceMeters <= 250;
      if (matchedPhrases.length > 0 && withinRadius) {
        passing.push({ cand, basis: 'NAME_AND_COORDINATE_CORROBORATION', tier: 3, distanceMeters });
      } else if (explicitRef && (matchedPhrases.length > 0 || withinRadius)) {
        passing.push({ cand, basis: 'EXPLICIT_POI_REF_AND_TEXT_MATCH', tier: 2, distanceMeters });
      } else if (matchedPhrases.length > 0 && matchedContextTerms.length > 0 && !mentionsForeign) {
        passing.push({ cand, basis: 'UNIQUE_NAME_AND_DESTINATION_CONTEXT', tier: 1, distanceMeters });
      } else {
        sawNameOnly = true;
      }
    }

    if (passing.length > 0) {
      passing.sort((a, b) => b.tier - a.tier);
      const winner = passing[0];
      return {
        status: 'LINKED',
        scope: 'POI',
        placeId: winner.cand.id,
        destinationId: winner.cand.destinationId,
        groundingBasis: winner.basis,
        decisionReason: 'verified_poi_grounding_passed',
        groundingEvidence: {
          dataGovernanceRole: 'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
          notPrimaryFactualCorpus: true,
          matchedPlaceId: winner.cand.id,
          destinationSlug: winner.cand.destination.slug,
          distanceMeters: winner.distanceMeters,
        },
      };
    }

    // City-level fallback: single verified destination mentioned, no conflicting city/coord conflict
    if (!sawCoordConflict && !sawCityConflict && !sawNameOnly && mentionedSlugs.length === 1) {
      const slug = mentionedSlugs[0];
      const dest = [...state.destinations.values()].find((d) => d.slug === slug);
      if (dest) {
        return {
          status: 'LINKED_CITY',
          scope: 'CITY',
          placeId: null,
          destinationId: dest.id,
          groundingBasis: 'SINGLE_DESTINATION_CONTEXT_FALLBACK',
          decisionReason: 'city_level_destination_grounding_passed',
          groundingEvidence: {
            dataGovernanceRole: 'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
            notPrimaryFactualCorpus: true,
            destinationSlug: dest.slug,
            destinationId: dest.id,
          },
        };
      }
    }

    let reason = 'no_poi_name_or_coordinate_match';
    if (sawCoordConflict) reason = 'coordinate_conflict_with_poi';
    else if (sawCityConflict) reason = 'conflicting_city_mention';
    else if (sawNameOnly) reason = 'missing_destination_or_spatial_corroboration';
    else if (mentionedSlugs.length > 1) reason = 'ambiguous_multiple_destinations';

    return {
      status: 'UNLINKED_NO_BASIS',
      scope: 'NONE',
      placeId: null,
      destinationId: null,
      groundingBasis: null,
      decisionReason: reason,
      groundingEvidence: {
        dataGovernanceRole: 'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
        notPrimaryFactualCorpus: true,
        mentionedDestinations: mentionedSlugs,
      },
    };
  }

  function upsertYoutubeEvent(normalized, nowMs = Date.now()) {
    const dedupeKey = normalized.eventId?.trim()
      ? `yt:event:${normalized.eventId.trim()}`
      : `yt:video:${normalized.videoId}:${(normalized.sourceUpdatedAt || normalized.publishedAt).toISOString()}`;

    const nowIso = new Date(nowMs).toISOString();
    const existing = state.youtubeUpdatesByDedupeKey.get(dedupeKey);
    if (existing) {
      existing.deliveryCount += 1;
      existing.lastReceivedAt = nowIso;
      existing.updatedAt = (existing.sourceUpdatedAt || existing.lastReceivedAt);
      return {
        id: existing.id,
        dedupeKey: existing.dedupeKey,
        videoId: existing.videoId,
        videoUrl: existing.videoUrl,
        duplicate: true,
        deliveryCount: existing.deliveryCount,
        status: existing.status,
        scope: existing.scope,
        linkedPlaceId: existing.placeId,
        destinationId: existing.destinationId,
        publishedAt: existing.publishedAt,
        receivedAt: existing.receivedAt,
        lastReceivedAt: existing.lastReceivedAt,
        updatedAt: existing.updatedAt,
        ingestLatencyMs: existing.ingestLatencyMs,
        groundingBasis: existing.groundingBasis,
        decisionReason: existing.decisionReason,
        groundingEvidence: existing.groundingEvidence,
      };
    }

    const decision = evaluateGrounding(normalized);
    const publishedIso = normalized.publishedAt.toISOString();
    const sourceUpdatedIso = normalized.sourceUpdatedAt ? normalized.sourceUpdatedAt.toISOString() : null;
    const receivedMs = nowMs;
    const ingestLatencyMs = Math.max(0, receivedMs - normalized.publishedAt.getTime());

    const record = {
      id: crypto.randomUUID(),
      dedupeKey,
      placeId: decision.placeId,
      destinationId: decision.destinationId,
      destinationSlug:
        decision.destinationId && state.destinations.get(decision.destinationId)?.slug
          ? state.destinations.get(decision.destinationId).slug
          : null,
      scope: decision.scope,
      status: decision.status,
      source: 'youtube',
      channelId: normalized.channelId,
      channelTitle: normalized.channelTitle || 'WanderAI Travel',
      videoId: normalized.videoId,
      videoUrl: `https://www.youtube.com/watch?v=${normalized.videoId}`,
      title: normalized.title,
      description: normalized.description || null,
      tags: normalized.tags || [],
      publishedAt: publishedIso,
      receivedAt: nowIso,
      lastReceivedAt: nowIso,
      sourceUpdatedAt: sourceUpdatedIso,
      updatedAt: sourceUpdatedIso || nowIso,
      ingestLatencyMs,
      deliveryLagMs: ingestLatencyMs,
      deliveryCount: 1,
      groundingBasis: decision.groundingBasis,
      decisionReason: decision.decisionReason,
      groundingEvidence: decision.groundingEvidence,
    };
    state.youtubeUpdatesByDedupeKey.set(dedupeKey, record);

    return {
      id: record.id,
      dedupeKey: record.dedupeKey,
      videoId: record.videoId,
      videoUrl: record.videoUrl,
      duplicate: false,
      deliveryCount: record.deliveryCount,
      status: record.status,
      scope: record.scope,
      linkedPlaceId: record.placeId,
      destinationId: record.destinationId,
      publishedAt: record.publishedAt,
      receivedAt: record.receivedAt,
      lastReceivedAt: record.lastReceivedAt,
      updatedAt: record.updatedAt,
      ingestLatencyMs: record.ingestLatencyMs,
      groundingBasis: record.groundingBasis,
      decisionReason: record.decisionReason,
      groundingEvidence: record.groundingEvidence,
    };
  }

  function toPublicYoutubeItem(r) {
    return {
      id: r.id,
      placeId: r.placeId,
      destinationId: r.destinationId,
      destinationSlug: r.destinationSlug,
      scope: r.scope,
      source: 'youtube',
      channelId: r.channelId,
      channelTitle: r.channelTitle,
      videoId: r.videoId,
      videoUrl: r.videoUrl,
      title: r.title,
      description: r.description,
      tags: r.tags,
      publishedAt: r.publishedAt,
      receivedAt: r.receivedAt,
      updatedAt: r.updatedAt,
      sourceUpdatedAt: r.sourceUpdatedAt,
      lastReceivedAt: r.lastReceivedAt,
      ingestLatencyMs: r.ingestLatencyMs,
      deliveryLagMs: r.deliveryLagMs,
      deliveryCount: r.deliveryCount,
      groundingBasis: r.groundingBasis,
      groundingEvidence: r.groundingEvidence,
    };
  }

  function sortAndDedupeYoutube(records, limit) {
    const sorted = [...records].sort(
      (a, b) =>
        Date.parse(b.publishedAt) - Date.parse(a.publishedAt) ||
        Date.parse(b.receivedAt) - Date.parse(a.receivedAt),
    );
    const seenVideoIds = new Set();
    const deduped = [];
    for (const r of sorted) {
      if (seenVideoIds.has(r.videoId)) continue;
      seenVideoIds.add(r.videoId);
      deduped.push(r);
      if (deduped.length >= limit) break;
    }
    return deduped.map(toPublicYoutubeItem);
  }

  function resolveEffectiveNowMs(req) {
    const rawNow = req.headers['x-e2e-test-now'];
    if (!rawNow) return Date.now();
    const parsed = Date.parse(String(rawNow));
    return Number.isFinite(parsed) ? parsed : Date.now();
  }

  async function readRawBody(req) {
    const chunks = [];
    for await (const chunk of req) {
      chunks.push(chunk);
    }
    return Buffer.concat(chunks).toString('utf8');
  }

  const server = http.createServer(async (req, res) => {
    const reqUrl = new URL(req.url, 'http://127.0.0.1');
    const reqPath = reqUrl.pathname;
    const method = req.method || 'GET';

    // Fault injection support for self-test transient 503 verification
    const injectStatus = Number(req.headers['x-e2e-inject-status'] || 0);
    if (injectStatus >= 400) {
      return sendError(
        res,
        injectStatus,
        injectStatus === 503 ? 'SERVICE_UNAVAILABLE' : 'INJECTED_ERROR',
        'Simulated transient backend error',
        reqPath,
      );
    }

    const rawBody = ['POST', 'PUT', 'PATCH'].includes(method) ? await readRawBody(req) : '';
    let jsonBody = null;
    const contentType = String(req.headers['content-type'] || '').toLowerCase();
    if (rawBody && contentType.includes('application/json')) {
      try {
        jsonBody = JSON.parse(rawBody);
      } catch {
        return sendError(res, 400, 'BAD_REQUEST', 'Invalid JSON body', reqPath);
      }
    }

    // --- Self-test inspection hooks (NOT used in --mode=live) ---
    if (reqPath === '/_test/reset' && method === 'POST') {
      const fresh = createInitialState();
      Object.assign(state, fresh);
      return sendSuccess(res, 200, { reset: true });
    }
    if (reqPath === '/_test/mail-outbox' && method === 'GET') {
      const email = reqUrl.searchParams.get('email')?.trim().toLowerCase();
      const items = email
        ? state.mailOutbox.filter((m) => m.to === email)
        : state.mailOutbox;
      return sendSuccess(res, 200, { items });
    }
    if (reqPath === '/_test/seed-expired-reset-token' && method === 'POST') {
      const email = String(jsonBody?.email || '').trim().toLowerCase();
      const user = state.usersByEmail.get(email);
      if (!user) return sendError(res, 404, 'USER_NOT_FOUND', 'User not found', reqPath);
      const rawToken = `expired-${crypto.randomUUID()}`;
      state.resetTokensByHash.set(sha256Hex(rawToken), {
        id: crypto.randomUUID(),
        userId: user.id,
        expiresAtMs: Date.now() - 60_000,
        usedAtMs: null,
      });
      return sendSuccess(res, 200, { token: rawToken });
    }
    if (reqPath === '/_test/db-stats' && method === 'GET') {
      return sendSuccess(res, 200, {
        documentsCount: state.documents.length,
        placeSourcesCount: state.placeSources.length,
        youtubePoiUpdatesCount: state.youtubeUpdatesByDedupeKey.size,
      });
    }

    // --- Health ---
    if (reqPath === '/health' && method === 'GET') {
      return sendSuccess(res, 200, {
        status: 'ok',
        timestamp: new Date().toISOString(),
        version: 'beta-self-test',
      });
    }

    // --- Auth ---
    if (reqPath === '/auth/register' && method === 'POST') {
      const email = String(jsonBody?.email || '').trim().toLowerCase();
      const password = String(jsonBody?.password || '');
      const name = String(jsonBody?.name || '').trim();
      if (!email || !email.includes('@') || password.length < 6 || !name) {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Dữ liệu đăng ký không hợp lệ', reqPath);
      }
      if (state.usersByEmail.has(email)) {
        return sendError(res, 400, 'EMAIL_ALREADY_EXISTS', 'Email đã được sử dụng.', reqPath);
      }
      const user = {
        id: crypto.randomUUID(),
        email,
        name,
        passwordHash: sha256Hex(password),
        role: 'USER',
        isVerified: true,
        providers: new Set(['local']),
        profile: { displayName: name, avatar: null, bio: null, phone: null },
        preferences: { interests: ['culture'], budgetMin: 0, budgetMax: 5000000 },
        createdAt: new Date().toISOString(),
      };
      state.usersById.set(user.id, user);
      state.usersByEmail.set(email, user);
      return sendSuccess(res, 201, issueTokensForUser(user));
    }

    if (reqPath === '/auth/login' && method === 'POST') {
      const email = String(jsonBody?.email || '').trim().toLowerCase();
      const password = String(jsonBody?.password || '');
      const user = state.usersByEmail.get(email);
      if (!user || !user.passwordHash || user.passwordHash !== sha256Hex(password)) {
        return sendError(
          res,
          401,
          'INVALID_CREDENTIALS',
          'Email hoặc mật khẩu không đúng.',
          reqPath,
        );
      }
      return sendSuccess(res, 200, issueTokensForUser(user));
    }

    if (reqPath === '/auth/refresh' && method === 'POST') {
      const allowedKeys = new Set(['refresh_token']);
      const extraKeys = Object.keys(jsonBody || {}).filter((k) => !allowedKeys.has(k));
      if (extraKeys.length > 0 || typeof jsonBody?.refresh_token !== 'string') {
        return sendError(
          res,
          400,
          'VALIDATION_ERROR',
          `property ${extraKeys[0] || 'refresh_token'} should not exist or invalid`,
          reqPath,
        );
      }
      const payload = verifyJwt(jsonBody.refresh_token);
      if (!payload || payload.type !== 'refresh') {
        return sendError(res, 401, 'INVALID_CREDENTIALS', 'Refresh token không hợp lệ', reqPath);
      }
      const user = state.usersById.get(payload.sub);
      if (!user) {
        return sendError(res, 401, 'INVALID_CREDENTIALS', 'User không tồn tại', reqPath);
      }
      return sendSuccess(res, 200, issueTokensForUser(user));
    }

    if (reqPath === '/auth/forgot-password' && method === 'POST') {
      const email = String(jsonBody?.email || '').trim().toLowerCase();
      if (!email || !email.includes('@')) {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Email không hợp lệ', reqPath);
      }
      const user = state.usersByEmail.get(email);
      if (user) {
        // Invalidate prior unused tokens for this user
        for (const tok of state.resetTokensByHash.values()) {
          if (tok.userId === user.id && tok.usedAtMs === null) {
            tok.usedAtMs = Date.now();
          }
        }
        const rawToken = `rst-${crypto.randomBytes(24).toString('hex')}`;
        state.resetTokensByHash.set(sha256Hex(rawToken), {
          id: crypto.randomUUID(),
          userId: user.id,
          expiresAtMs: Date.now() + 30 * 60 * 1000,
          usedAtMs: null,
        });
        state.mailOutbox.push({
          to: email,
          subject: 'Đặt lại mật khẩu WanderAI',
          rawToken,
          resetUrl: `/reset-password?token=${rawToken}`,
          sentAt: new Date().toISOString(),
        });
      }
      return sendSuccess(res, 200, {
        sent: true,
        message: 'Nếu email tồn tại trong hệ thống, liên kết đặt lại mật khẩu đã được gửi.',
        expiresInMinutes: 30,
      });
    }

    if (reqPath === '/auth/reset-password/validate' && method === 'GET') {
      const rawToken = reqUrl.searchParams.get('token') || '';
      const entry = rawToken ? state.resetTokensByHash.get(sha256Hex(rawToken)) : null;
      if (!entry) {
        return sendError(
          res,
          400,
          'RESET_TOKEN_INVALID',
          'Liên kết đặt lại mật khẩu không hợp lệ.',
          reqPath,
        );
      }
      if (entry.usedAtMs !== null) {
        return sendError(
          res,
          410,
          'RESET_TOKEN_USED',
          'Liên kết đặt lại mật khẩu đã được sử dụng hoặc bị thay thế.',
          reqPath,
        );
      }
      if (Date.now() > entry.expiresAtMs) {
        return sendError(
          res,
          410,
          'RESET_TOKEN_EXPIRED',
          'Liên kết đặt lại mật khẩu đã hết hạn.',
          reqPath,
        );
      }
      return sendSuccess(res, 200, {
        valid: true,
        expiresAt: new Date(entry.expiresAtMs).toISOString(),
      });
    }

    if (reqPath === '/auth/reset-password' && method === 'POST') {
      const rawToken = String(jsonBody?.token || '');
      const newPassword = String(jsonBody?.newPassword || '');
      const entry = rawToken ? state.resetTokensByHash.get(sha256Hex(rawToken)) : null;
      if (!entry) {
        return sendError(
          res,
          400,
          'RESET_TOKEN_INVALID',
          'Liên kết đặt lại mật khẩu không hợp lệ.',
          reqPath,
        );
      }
      if (entry.usedAtMs !== null) {
        return sendError(
          res,
          410,
          'RESET_TOKEN_USED',
          'Liên kết đặt lại mật khẩu đã được sử dụng.',
          reqPath,
        );
      }
      if (Date.now() > entry.expiresAtMs) {
        return sendError(
          res,
          410,
          'RESET_TOKEN_EXPIRED',
          'Liên kết đặt lại mật khẩu đã hết hạn.',
          reqPath,
        );
      }
      if (newPassword.length < 6) {
        return sendError(
          res,
          400,
          'VALIDATION_ERROR',
          'Mật khẩu mới phải có ít nhất 6 ký tự.',
          reqPath,
        );
      }
      entry.usedAtMs = Date.now();
      const user = state.usersById.get(entry.userId);
      user.passwordHash = sha256Hex(newPassword);
      user.providers.add('local');
      return sendSuccess(res, 200, {
        reset: true,
        message: 'Mật khẩu đã được cập nhật thành công.',
      });
    }

    if (
      (reqPath === '/auth/oauth/google' || reqPath === '/auth/oauth/facebook') &&
      method === 'POST'
    ) {
      const provider = reqPath.endsWith('/google') ? 'google' : 'facebook';
      const token =
        provider === 'google' ? jsonBody?.idToken : jsonBody?.accessToken;
      if (!token || typeof token !== 'string') {
        return sendError(res, 401, 'OAUTH_TOKEN_INVALID', 'Thiếu token OAuth', reqPath);
      }
      if (token.startsWith('provider-error')) {
        return sendError(
          res,
          502,
          'OAUTH_PROVIDER_ERROR',
          'Lỗi kết nối nhà cung cấp OAuth',
          reqPath,
        );
      }
      if (token.startsWith('bad-')) {
        return sendError(
          res,
          401,
          'OAUTH_TOKEN_INVALID',
          'Token OAuth không hợp lệ hoặc đã hết hạn',
          reqPath,
        );
      }
      if (token.startsWith('no-email')) {
        return sendError(
          res,
          400,
          'OAUTH_EMAIL_UNAVAILABLE',
          'Tài khoản OAuth chưa cấp quyền email đã xác minh',
          reqPath,
        );
      }

      // Deterministic token-to-profile mapping for valid-* tokens
      let email = `${provider}.user@gomate.vn`;
      let name = provider === 'google' ? 'Google Traveler' : 'Facebook Traveler';
      let providerUserId = `${provider}-sub-${sha256Hex(token).slice(0, 8)}`;

      if (token === 'valid-google-token') {
        email = 'g101@gomate.vn';
        name = 'Google Traveler';
        providerUserId = 'g-101';
      } else if (token === 'valid-fb-token') {
        email = 'fb202@gomate.vn';
        name = 'FB Traveler';
        providerUserId = 'fb-202';
      } else if (token.startsWith('valid-email:')) {
        email = token.slice('valid-email:'.length).trim().toLowerCase();
      }

      const linkKey = `${provider}:${providerUserId}`;
      let user =
        state.oauthLinks.has(linkKey)
          ? state.usersById.get(state.oauthLinks.get(linkKey))
          : state.usersByEmail.get(email);

      if (!user) {
        user = {
          id: crypto.randomUUID(),
          email,
          name,
          passwordHash: null,
          role: 'USER',
          isVerified: true,
          providers: new Set([provider]),
          profile: { displayName: name, avatar: null, bio: null, phone: null },
          preferences: { interests: ['culture'], budgetMin: 0, budgetMax: 5000000 },
          createdAt: new Date().toISOString(),
        };
        state.usersById.set(user.id, user);
        state.usersByEmail.set(email, user);
      } else {
        user.providers.add(provider);
      }
      state.oauthLinks.set(linkKey, user.id);
      const tokens = issueTokensForUser(user);
      return sendSuccess(res, 200, {
        ...tokens,
        user: sanitizeUser(user),
      });
    }

    // --- Users ---
    if (reqPath === '/users/me' && method === 'GET') {
      const user = getAuthUser(req);
      if (!user) return sendError(res, 401, 'UNAUTHORIZED', 'Unauthorized', reqPath);
      return sendSuccess(res, 200, {
        ...sanitizeUser(user),
        createdAt: user.createdAt,
        profile: user.profile,
        preferences: user.preferences,
      });
    }

    // --- Destinations ---
    if (reqPath === '/destinations' && method === 'GET') {
      const items = [...state.destinations.values()];
      return sendSuccess(res, 200, {
        items,
        total: items.length,
        page: 1,
        limit: 20,
        totalPages: 1,
      });
    }

    const destYtMatch = reqPath.match(
      /^\/(?:youtube\/)?destinations\/([^/]+)\/(?:youtube-updates|updates)$/,
    );
    if (destYtMatch && method === 'GET') {
      const idOrSlug = decodeURIComponent(destYtMatch[1]);
      const dest = [...state.destinations.values()].find(
        (d) => d.id === idOrSlug || d.slug === idOrSlug,
      );
      if (!dest) {
        return sendError(
          res,
          404,
          'DESTINATION_NOT_FOUND',
          `Destination not found: ${idOrSlug}`,
          reqPath,
        );
      }
      const limit = Math.min(50, Math.max(1, Number(reqUrl.searchParams.get('limit') || 10)));
      const nowMs = resolveEffectiveNowMs(req);
      const items = sortAndDedupeYoutube(
        [...state.youtubeUpdatesByDedupeKey.values()].filter(
          (u) => u.destinationId === dest.id && u.scope === 'CITY',
        ),
        limit,
      );

      return sendSuccess(res, 200, {
        destinationId: dest.id,
        destinationSlug: dest.slug,
        destinationName: dest.name,
        governanceRole: 'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
        notPrimaryFactualCorpus: true,
        serverDeliveredAt: new Date(nowMs).toISOString(),
        realtimeSlaMaxLatencyMs: 300000,
        total: items.length,
        items,
      });
    }

    // --- Places ---
    if (reqPath === '/places' && method === 'GET') {
      const page = Math.max(1, Number(reqUrl.searchParams.get('page') || 1));
      const limit = Math.min(100, Math.max(1, Number(reqUrl.searchParams.get('limit') || 20)));
      const search = (reqUrl.searchParams.get('search') || '').trim();
      const destinationId = reqUrl.searchParams.get('destinationId');
      const verifiedOnly = reqUrl.searchParams.get('verifiedOnly') !== 'false';

      let list = [...state.places.values()];
      if (verifiedOnly) {
        list = list.filter((p) => p.placeSources.length > 0);
      }
      if (destinationId) {
        list = list.filter((p) => p.destinationId === destinationId);
      }
      if (search) {
        const needle = foldVietnamese(search);
        list = list.filter(
          (p) =>
            foldVietnamese(p.name).includes(needle) ||
            foldVietnamese(p.nameEn || '').includes(needle),
        );
      }
      const total = list.length;
      const start = (page - 1) * limit;
      const items = list.slice(start, start + limit);
      return sendSuccess(res, 200, {
        items,
        total,
        page,
        limit,
        totalPages: Math.max(1, Math.ceil(total / limit)),
      });
    }

    const placeYtMatch = reqPath.match(
      /^\/(?:places\/([^/]+)\/youtube-updates|youtube\/places\/([^/]+)\/updates)$/,
    );
    if (placeYtMatch && method === 'GET') {
      const placeId = placeYtMatch[1] || placeYtMatch[2];
      if (!UUID_RE.test(placeId)) {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Invalid UUID', reqPath);
      }
      const place = state.places.get(placeId);
      if (!place || place.placeSources.length === 0) {
        return sendError(res, 404, 'PLACE_NOT_FOUND', 'Place not found or unverified', reqPath);
      }
      const limit = Math.min(50, Math.max(1, Number(reqUrl.searchParams.get('limit') || 10)));
      const nowMs = resolveEffectiveNowMs(req);
      const poiItems = sortAndDedupeYoutube(
        [...state.youtubeUpdatesByDedupeKey.values()].filter(
          (u) => u.scope === 'POI' && u.placeId === place.id,
        ),
        limit,
      );
      const cityFallbackItems = sortAndDedupeYoutube(
        [...state.youtubeUpdatesByDedupeKey.values()].filter(
          (u) => u.scope === 'CITY' && u.destinationId === place.destinationId,
        ),
        limit,
      );

      return sendSuccess(res, 200, {
        placeId: place.id,
        placeName: place.name,
        destinationId: place.destinationId,
        destinationSlug: place.destination.slug,
        destinationName: place.destination.name,
        governanceRole: 'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
        notPrimaryFactualCorpus: true,
        serverDeliveredAt: new Date(nowMs).toISOString(),
        realtimeSlaMaxLatencyMs: 300000,
        total: poiItems.length,
        items: poiItems,
        cityFallbackTotal: cityFallbackItems.length,
        cityFallbackItems,
      });
    }

    const placeByIdMatch = reqPath.match(/^\/places\/([^/]+)$/);
    if (placeByIdMatch && method === 'GET') {
      const placeId = placeByIdMatch[1];
      if (!UUID_RE.test(placeId)) {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Invalid UUID', reqPath);
      }
      const place = state.places.get(placeId);
      if (!place || place.placeSources.length === 0) {
        return sendError(res, 404, 'PLACE_NOT_FOUND', 'Place not found', reqPath);
      }
      return sendSuccess(res, 200, place);
    }

    // --- Trips ---
    if (reqPath === '/trips' && method === 'POST') {
      const user = getAuthUser(req);
      if (!user) return sendError(res, 401, 'UNAUTHORIZED', 'Unauthorized', reqPath);
      const title = String(jsonBody?.title || '').trim();
      if (!title) return sendError(res, 400, 'VALIDATION_ERROR', 'Title is required', reqPath);
      const trip = {
        id: crypto.randomUUID(),
        title,
        ownerId: user.id,
        destinationId: jsonBody?.destinationId || HALONG_FIXTURE.destinations.haLong.id,
        destination: state.destinations.get(
          jsonBody?.destinationId || HALONG_FIXTURE.destinations.haLong.id,
        ) || HALONG_FIXTURE.destinations.haLong,
        status: 'DRAFT',
        itineraries: [{ dayNumber: 1, items: [] }],
        members: [{ userId: user.id, role: 'OWNER' }],
        createdAt: new Date().toISOString(),
      };
      state.trips.set(trip.id, trip);
      return sendSuccess(res, 201, trip);
    }

    if (reqPath === '/trips' && method === 'GET') {
      const user = getAuthUser(req);
      if (!user) return sendError(res, 401, 'UNAUTHORIZED', 'Unauthorized', reqPath);
      const list = [...state.trips.values()].filter((t) =>
        t.members.some((m) => m.userId === user.id),
      );
      return sendSuccess(res, 200, list);
    }

    const tripDetailMatch = reqPath.match(/^\/trips\/([^/]+)$/);
    if (tripDetailMatch && method === 'GET') {
      const user = getAuthUser(req);
      if (!user) return sendError(res, 401, 'UNAUTHORIZED', 'Unauthorized', reqPath);
      const trip = state.trips.get(tripDetailMatch[1]);
      if (!trip) return sendError(res, 404, 'TRIP_NOT_FOUND', 'Trip not found', reqPath);
      if (!trip.members.some((m) => m.userId === user.id)) {
        return sendError(res, 403, 'FORBIDDEN', 'Forbidden', reqPath);
      }
      return sendSuccess(res, 200, trip);
    }

    const tripItineraryMatch = reqPath.match(/^\/trips\/([^/]+)\/itinerary$/);
    if (tripItineraryMatch && method === 'POST') {
      const user = getAuthUser(req);
      if (!user) return sendError(res, 401, 'UNAUTHORIZED', 'Unauthorized', reqPath);
      const trip = state.trips.get(tripItineraryMatch[1]);
      if (!trip) return sendError(res, 404, 'TRIP_NOT_FOUND', 'Trip not found', reqPath);
      if (!trip.members.some((m) => m.userId === user.id)) {
        return sendError(res, 403, 'FORBIDDEN', 'Forbidden', reqPath);
      }
      const dayNumber = Number(jsonBody?.dayNumber || 1);
      if (dayNumber < 1 || !jsonBody?.activity) {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Invalid itinerary payload', reqPath);
      }
      let dayObj = trip.itineraries.find((d) => d.dayNumber === dayNumber);
      if (!dayObj) {
        dayObj = { dayNumber, items: [] };
        trip.itineraries.push(dayObj);
      }
      const place = jsonBody.placeId ? state.places.get(jsonBody.placeId) || null : null;
      const item = {
        id: crypto.randomUUID(),
        dayNumber,
        activity: jsonBody.activity,
        placeId: jsonBody.placeId || null,
        place,
      };
      dayObj.items.push(item);
      return sendSuccess(res, 201, item);
    }

    // --- YouTube Ingestion ---
    if (reqPath === '/youtube/webhook' && method === 'GET') {
      const mode = reqUrl.searchParams.get('hub.mode');
      const topic = reqUrl.searchParams.get('hub.topic') || '';
      const challenge = reqUrl.searchParams.get('hub.challenge') || '';
      const token = reqUrl.searchParams.get('hub.verify_token') || '';
      if (mode !== 'subscribe' && mode !== 'unsubscribe') {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Invalid hub.mode', reqPath);
      }
      if (
        !/^https:\/\/www\.youtube\.com\/xml\/feeds\/videos\.xml\?channel_id=[A-Za-z0-9_-]+$/.test(
          topic,
        )
      ) {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Invalid hub.topic', reqPath);
      }
      if (!challenge) {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Missing hub.challenge', reqPath);
      }
      if (verifyToken && token !== verifyToken) {
        return sendError(res, 403, 'FORBIDDEN', 'Invalid hub.verify_token', reqPath);
      }
      res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end(challenge);
      return;
    }

    if (reqPath === '/youtube/webhook' && method === 'POST') {
      if (websubSecret) {
        const sigHeader = String(req.headers['x-hub-signature'] || '');
        if (!sigHeader.includes('=')) {
          return sendError(res, 401, 'UNAUTHORIZED', 'Missing X-Hub-Signature', reqPath);
        }
        const [algo, providedHex] = sigHeader.split('=', 2);
        if (!['sha1', 'sha256'].includes(algo.toLowerCase())) {
          return sendError(res, 401, 'UNAUTHORIZED', 'Unsupported WebSub algorithm', reqPath);
        }
        const expectedHex = crypto
          .createHmac(algo.toLowerCase(), websubSecret)
          .update(rawBody, 'utf8')
          .digest('hex');
        const a = Buffer.from(expectedHex, 'utf8');
        const b = Buffer.from(providedHex.toLowerCase(), 'utf8');
        if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) {
          return sendError(res, 401, 'UNAUTHORIZED', 'Invalid X-Hub-Signature', reqPath);
        }
      }
      const parsed = parseAtomFeed(rawBody);
      if (parsed.error) {
        return sendError(res, parsed.error.status, 'VALIDATION_ERROR', parsed.error.message, reqPath);
      }
      const nowMs = resolveEffectiveNowMs(req);
      const results = parsed.entries.map((e) => upsertYoutubeEvent(e, nowMs));
      return sendSuccess(res, 200, { processedCount: results.length, results });
    }

    if (reqPath === '/youtube/events' && method === 'POST') {
      if (youtubeSecret) {
        const providedSecret = req.headers['x-youtube-internal-secret'];
        if (!providedSecret || providedSecret !== youtubeSecret) {
          return sendError(
            res,
            401,
            'YOUTUBE_EVENT_UNAUTHORIZED',
            'Invalid or missing x-youtube-internal-secret',
            reqPath,
          );
        }
      }

      const dto = jsonBody || {};
      const hasLat = typeof dto.latitude === 'number';
      const hasLon = typeof dto.longitude === 'number';
      if (hasLat !== hasLon) {
        return sendError(
          res,
          400,
          'VALIDATION_ERROR',
          'Both latitude and longitude must be provided together',
          reqPath,
        );
      }
      if (!dto.videoId || !YOUTUBE_VIDEO_ID_RE.test(dto.videoId)) {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Invalid videoId', reqPath);
      }
      if (!dto.channelId || !dto.title) {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Missing channelId or title', reqPath);
      }
      if (
        !dto.publishedAt ||
        !EXPLICIT_TZ_ISO_RE.test(dto.publishedAt) ||
        Number.isNaN(Date.parse(dto.publishedAt))
      ) {
        return sendError(
          res,
          400,
          'VALIDATION_ERROR',
          'publishedAt must be ISO-8601 with explicit timezone',
          reqPath,
        );
      }
      const sourceUpdatedAt = dto.sourceUpdatedAt ? new Date(dto.sourceUpdatedAt) : null;
      if (
        dto.sourceUpdatedAt &&
        (!EXPLICIT_TZ_ISO_RE.test(dto.sourceUpdatedAt) || Number.isNaN(sourceUpdatedAt.getTime()))
      ) {
        return sendError(res, 400, 'VALIDATION_ERROR', 'Invalid sourceUpdatedAt', reqPath);
      }

      const receipt = upsertYoutubeEvent(
        {
          eventId: dto.eventId,
          videoId: dto.videoId,
          channelId: dto.channelId,
          channelTitle: dto.channelTitle || null,
          title: String(dto.title).trim(),
          description: dto.description ? String(dto.description).trim() : null,
          tags: Array.isArray(dto.tags) ? dto.tags : [],
          publishedAt: new Date(dto.publishedAt),
          sourceUpdatedAt,
          latitude: hasLat ? dto.latitude : null,
          longitude: hasLon ? dto.longitude : null,
          candidatePlaceId: dto.candidatePlaceId || null,
        },
        resolveEffectiveNowMs(req),
      );
      return sendSuccess(res, 200, receipt);
    }

    return sendError(res, 404, 'NOT_FOUND', `Route not found: ${method} ${reqPath}`, reqPath);
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const addr = server.address();
  const baseUrl = `http://127.0.0.1:${addr.port}`;

  return {
    baseUrl,
    close: () =>
      new Promise((resolve, reject) =>
        server.close((err) => (err ? reject(err) : resolve())),
      ),
  };
}
