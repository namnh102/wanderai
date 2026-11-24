import {
  BadRequestException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import {
  Prisma,
  YoutubePoiUpdate,
  YoutubeUpdateScope,
  YoutubeUpdateStatus,
} from "@prisma/client";
import * as fs from "fs";
import * as path from "path";
import { YOUTUBE_ERROR_CODES } from "../../common/constants/youtube-error-codes";
import { PrismaService } from "../../prisma/prisma.service";
import { osmAddress } from "../places/osm-tags";
import { IngestYoutubeEventDto } from "./dto/youtube-update.dto";
import {
  computeYoutubeDedupeKey,
  evaluatePoiGrounding,
  extractVerifiedAliasesFromDescription,
  NormalizedYoutubeEventInput,
  parseYoutubeAtomFeed,
  VerifiedDestinationCandidate,
  VerifiedPlaceCandidate,
  verifyWebSubSignature,
} from "./youtube-grounding";

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const DEFAULT_REALTIME_SLA_MAX_LATENCY_MS = 300_000;

export interface YoutubeIngestionReceipt {
  id: string;
  dedupeKey: string;
  videoId: string;
  videoUrl: string;
  duplicate: boolean;
  deliveryCount: number;
  publishedAt: string;
  receivedAt: string;
  lastReceivedAt: string;
  status: YoutubeUpdateStatus;
  scope: YoutubeUpdateScope;
  linkedPlaceId: string | null;
  destinationId: string | null;
  groundingBasis: string | null;
  decisionReason: string;
  groundingEvidence: unknown;
}

export interface YoutubeSerializedUpdateItem {
  id: string;
  placeId: string | null;
  destinationId: string | null;
  destinationSlug: string | null;
  scope: "POI" | "CITY";
  source: "youtube";
  channelId: string;
  channelTitle: string | null;
  videoId: string;
  videoUrl: string;
  title: string;
  description: string | null;
  tags: string[];
  publishedAt: string;
  receivedAt: string;
  updatedAt: string;
  sourceUpdatedAt: string | null;
  lastReceivedAt: string;
  ingestLatencyMs: number;
  deliveryLagMs: number;
  groundingBasis: string | null;
  groundingEvidence: unknown;
}

@Injectable()
export class YoutubeService {
  private pilotDescriptionsCache: Map<string, string> | null = null;

  constructor(
    private readonly prisma: PrismaService,
    private readonly configService: ConfigService,
  ) {}

  private _getPilotDescriptionsMap(): Map<string, string> {
    if (this.pilotDescriptionsCache) return this.pilotDescriptionsCache;
    const map = new Map<string, string>();
    const candidatePaths = [
      path.resolve(
        __dirname,
        "../../../../data/enrichment/poi_enrichment_pilot_60_v1.json",
      ),
      path.resolve(
        process.cwd(),
        "data/enrichment/poi_enrichment_pilot_60_v1.json",
      ),
      path.resolve(
        process.cwd(),
        "../../data/enrichment/poi_enrichment_pilot_60_v1.json",
      ),
    ];
    for (const p of candidatePaths) {
      if (!fs.existsSync(p)) continue;
      try {
        const parsed = JSON.parse(fs.readFileSync(p, "utf-8")) as {
          items?: Array<{ place_id?: string; description?: string | null }>;
        };
        for (const item of parsed.items ?? []) {
          if (item.place_id && item.description) {
            map.set(item.place_id, item.description);
          }
        }
        break;
      } catch {
        // Optional enrichment manifest on stripped containers
      }
    }
    this.pilotDescriptionsCache = map;
    return map;
  }

  verifyWebSubHandshake(query: Record<string, string | undefined>): string {
    const mode = query["hub.mode"];
    const topic = query["hub.topic"];
    const challenge = query["hub.challenge"];
    const verifyToken = query["hub.verify_token"];

    if (mode !== "subscribe" && mode !== "unsubscribe") {
      throw new BadRequestException(
        "Invalid hub.mode; expected subscribe or unsubscribe",
      );
    }
    if (
      !topic ||
      !/^https:\/\/www\.youtube\.com\/xml\/feeds\/videos\.xml\?channel_id=[A-Za-z0-9_-]+$/.test(
        topic,
      )
    ) {
      throw new BadRequestException("Invalid YouTube WebSub hub.topic URL");
    }
    if (!challenge || challenge.length > 512) {
      throw new BadRequestException("Missing or invalid hub.challenge");
    }

    const expectedToken = this.configService.get<string>(
      "YOUTUBE_WEBSUB_VERIFY_TOKEN",
    );
    if (
      expectedToken &&
      expectedToken.trim() &&
      verifyToken !== expectedToken.trim()
    ) {
      throw new ForbiddenException({
        message: "Invalid hub.verify_token",
        errorCode: YOUTUBE_ERROR_CODES.YOUTUBE_EVENT_UNAUTHORIZED,
      });
    }

    return challenge;
  }

  async ingestAtomWebhook(
    rawXml: string,
    signatureHeader?: string,
  ): Promise<{ processedCount: number; results: YoutubeIngestionReceipt[] }> {
    const secret = this.configService.get<string>("YOUTUBE_WEBSUB_SECRET");
    verifyWebSubSignature(rawXml, signatureHeader, secret);

    if (!rawXml || !rawXml.trim()) {
      throw new BadRequestException(
        "Expected Atom XML body (Content-Type: application/atom+xml or text/xml)",
      );
    }

    const entries = parseYoutubeAtomFeed(rawXml);
    const results: YoutubeIngestionReceipt[] = [];
    for (const entry of entries) {
      const receipt = await this._ingestNormalizedEvent(entry, {
        transport: "websub_atom_xml",
        videoId: entry.videoId,
        channelId: entry.channelId,
        publishedAt: entry.publishedAt.toISOString(),
        sourceUpdatedAt: entry.sourceUpdatedAt?.toISOString() ?? null,
      });
      results.push(receipt);
    }

    return {
      processedCount: results.length,
      results,
    };
  }

  async ingestJsonEvent(
    dto: IngestYoutubeEventDto,
  ): Promise<YoutubeIngestionReceipt> {
    const hasLat = typeof dto.latitude === "number";
    const hasLon = typeof dto.longitude === "number";
    if (hasLat !== hasLon) {
      throw new BadRequestException(
        "Both latitude and longitude must be provided together when coordinates are present",
      );
    }

    const publishedAt = new Date(dto.publishedAt);
    if (Number.isNaN(publishedAt.getTime())) {
      throw new BadRequestException("Invalid publishedAt timestamp");
    }
    const sourceUpdatedAt = dto.sourceUpdatedAt
      ? new Date(dto.sourceUpdatedAt)
      : null;
    if (sourceUpdatedAt && Number.isNaN(sourceUpdatedAt.getTime())) {
      throw new BadRequestException("Invalid sourceUpdatedAt timestamp");
    }

    const normalized: NormalizedYoutubeEventInput = {
      eventId: dto.eventId,
      videoId: dto.videoId,
      channelId: dto.channelId,
      channelTitle: dto.channelTitle ?? null,
      title: dto.title.trim(),
      description: dto.description?.trim() ?? null,
      tags: (dto.tags ?? []).map((t) => t.trim()).filter(Boolean),
      publishedAt,
      sourceUpdatedAt,
      latitude: hasLat ? (dto.latitude ?? null) : null,
      longitude: hasLon ? (dto.longitude ?? null) : null,
      candidatePlaceId: dto.candidatePlaceId ?? null,
    };

    return this._ingestNormalizedEvent(normalized, {
      transport: "json_event",
      ...dto,
    });
  }

  private async _loadVerifiedPlaceCandidates(): Promise<
    VerifiedPlaceCandidate[]
  > {
    const pilotDescriptions = this._getPilotDescriptionsMap();
    const rows = await this.prisma.place.findMany({
      where: {
        deletedAt: null,
        placeSources: { some: {} },
      },
        select: {
          id: true,
          destinationId: true,
          name: true,
          nameEn: true,
          description: true,
          latitude: true,
          longitude: true,
          destination: {
            select: {
              id: true,
              name: true,
              slug: true,
              province: true,
            },
          },
          placeSources: {
            select: {
              sourceName: true,
              sourceId: true,
              rawData: true,
            },
          },
        },
      });

    return rows.map((r) => {
      const osmSource = r.placeSources.find((s) => s.sourceName === "osm");
      const factualAddress = osmAddress(
        (osmSource?.rawData ?? null) as Record<string, unknown> | null,
      );
      const descForAliases =
        r.description ?? pilotDescriptions.get(r.id) ?? null;
      return {
        id: r.id,
        destinationId: r.destination?.id ?? r.destinationId,
        name: r.name,
        nameEn: r.nameEn,
        address: factualAddress,
        latitude: r.latitude,
        longitude: r.longitude,
        destinationName: r.destination.name,
        destinationSlug: r.destination.slug,
        province: r.destination.province,
        provenanceSources: r.placeSources.map((s) => ({
          sourceName: s.sourceName,
          sourceId: s.sourceId,
          canonicalUrl:
            s.sourceName === "osm"
              ? `https://www.openstreetmap.org/${s.sourceId}`
              : null,
        })),
        verifiedAliases: extractVerifiedAliasesFromDescription(
          r.name,
          descForAliases,
        ),
      };
    });
  }

  private async _loadVerifiedDestinations(): Promise<
    VerifiedDestinationCandidate[]
  > {
    if (!this.prisma.destination?.findMany) {
      return [];
    }
    return this.prisma.destination.findMany({
      where: { deletedAt: null },
      select: {
        id: true,
        name: true,
        nameEn: true,
        slug: true,
        province: true,
        latitude: true,
        longitude: true,
      },
    });
  }

  private async _recordDuplicateDelivery(
    dedupeKey: string,
    existingRow?: YoutubePoiUpdate | null,
  ): Promise<YoutubePoiUpdate> {
    const currentRow =
      existingRow ??
      (await this.prisma.youtubePoiUpdate.findUnique({
        where: { dedupeKey },
      }));
    const nowMs = Date.now();
    const safeLastReceivedAt = currentRow
      ? new Date(
          Math.max(
            nowMs,
            currentRow.receivedAt.getTime(),
            currentRow.lastReceivedAt.getTime(),
          ),
        )
      : new Date(nowMs);

    return this.prisma.youtubePoiUpdate.update({
      where: { dedupeKey },
      data: {
        deliveryCount: { increment: 1 },
        lastReceivedAt: safeLastReceivedAt,
      },
    });
  }

  private _toReceipt(
    row: YoutubePoiUpdate,
    duplicate: boolean,
  ): YoutubeIngestionReceipt {
    const resolvedScope =
      row.scope ??
      (row.status === YoutubeUpdateStatus.LINKED
        ? YoutubeUpdateScope.POI
        : row.status === YoutubeUpdateStatus.LINKED_CITY
          ? YoutubeUpdateScope.CITY
          : YoutubeUpdateScope.NONE);

    return {
      id: row.id,
      dedupeKey: row.dedupeKey,
      videoId: row.videoId,
      videoUrl: row.videoUrl,
      duplicate,
      deliveryCount: row.deliveryCount,
      publishedAt: row.publishedAt.toISOString(),
      receivedAt: row.receivedAt.toISOString(),
      lastReceivedAt: row.lastReceivedAt.toISOString(),
      status: row.status,
      scope: resolvedScope,
      linkedPlaceId: row.placeId,
      destinationId: row.destinationId ?? null,
      groundingBasis: row.groundingBasis,
      decisionReason: row.decisionReason,
      groundingEvidence: row.groundingEvidence,
    };
  }

  private async _ingestNormalizedEvent(
    event: NormalizedYoutubeEventInput,
    rawPayload: Record<string, unknown>,
  ): Promise<YoutubeIngestionReceipt> {
    const receivedAt = new Date();
    const dedupeKey = computeYoutubeDedupeKey({
      eventId: event.eventId,
      videoId: event.videoId,
      publishedAt: event.publishedAt,
      sourceUpdatedAt: event.sourceUpdatedAt,
    });

    const existing = await this.prisma.youtubePoiUpdate.findUnique({
      where: { dedupeKey },
    });
    if (existing) {
      const updated = await this._recordDuplicateDelivery(dedupeKey, existing);
      return this._toReceipt(updated, true);
    }

    const [candidates, destinations] = await Promise.all([
      this._loadVerifiedPlaceCandidates(),
      this._loadVerifiedDestinations(),
    ]);
    const decision = evaluatePoiGrounding(event, candidates, destinations);
    const canonicalVideoUrl = `https://www.youtube.com/watch?v=${event.videoId}`;
    const prismaStatus =
      decision.status === "LINKED"
        ? YoutubeUpdateStatus.LINKED
        : decision.status === "LINKED_CITY"
          ? YoutubeUpdateStatus.LINKED_CITY
          : YoutubeUpdateStatus.UNLINKED_NO_BASIS;
    const prismaScope =
      decision.scope === "POI"
        ? YoutubeUpdateScope.POI
        : decision.scope === "CITY"
          ? YoutubeUpdateScope.CITY
          : YoutubeUpdateScope.NONE;

    try {
      const created = await this.prisma.youtubePoiUpdate.create({
        data: {
          dedupeKey,
          videoId: event.videoId,
          channelId: event.channelId,
          channelTitle: event.channelTitle ?? null,
          videoUrl: canonicalVideoUrl,
          title: event.title,
          description: event.description ?? null,
          tags: event.tags,
          latitude: event.latitude ?? null,
          longitude: event.longitude ?? null,
          publishedAt: event.publishedAt,
          sourceUpdatedAt: event.sourceUpdatedAt ?? null,
          receivedAt,
          lastReceivedAt: receivedAt,
          deliveryCount: 1,
          status: prismaStatus,
          scope: prismaScope,
          placeId: decision.placeId,
          destinationId: decision.destinationId,
          groundingBasis: decision.groundingBasis,
          decisionReason: decision.decisionReason,
          groundingEvidence:
            decision.groundingEvidence as Prisma.InputJsonValue,
          rawPayload: rawPayload as Prisma.InputJsonValue,
        },
      });
      return this._toReceipt(created, false);
    } catch (err) {
      if (
        err instanceof Prisma.PrismaClientKnownRequestError &&
        err.code === "P2002"
      ) {
        const updated = await this._recordDuplicateDelivery(dedupeKey);
        return this._toReceipt(updated, true);
      }
      throw err;
    }
  }

  private _getRealtimeSlaMaxLatencyMs(): number {
    const raw = this.configService.get<string | number>(
      "YOUTUBE_REALTIME_SLA_MAX_LATENCY_MS",
    );
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed > 0) {
      return Math.floor(parsed);
    }
    return DEFAULT_REALTIME_SLA_MAX_LATENCY_MS;
  }

  private _serializeUpdateItem(
    row: YoutubePoiUpdate,
    destinationMeta: { id: string | null; slug: string | null },
  ): YoutubeSerializedUpdateItem {
    const updatedAtDate =
      row.sourceUpdatedAt ?? row.lastReceivedAt ?? row.receivedAt;
    const isCity =
      row.scope === YoutubeUpdateScope.CITY ||
      row.status === YoutubeUpdateStatus.LINKED_CITY;
    const ingestLatencyMs = Math.max(
      0,
      row.receivedAt.getTime() - row.publishedAt.getTime(),
    );
    const deliveryLagMs = Math.max(
      0,
      row.lastReceivedAt.getTime() - row.publishedAt.getTime(),
    );

    return {
      id: row.id,
      placeId: isCity ? null : (row.placeId ?? null),
      destinationId: row.destinationId ?? destinationMeta.id ?? null,
      destinationSlug: destinationMeta.slug ?? null,
      scope: isCity ? "CITY" : "POI",
      source: "youtube",
      channelId: row.channelId,
      channelTitle: row.channelTitle,
      videoId: row.videoId,
      videoUrl: row.videoUrl,
      title: row.title,
      description: row.description,
      tags: row.tags,
      publishedAt: row.publishedAt.toISOString(),
      receivedAt: row.receivedAt.toISOString(),
      updatedAt: updatedAtDate.toISOString(),
      sourceUpdatedAt: row.sourceUpdatedAt
        ? row.sourceUpdatedAt.toISOString()
        : null,
      lastReceivedAt: row.lastReceivedAt.toISOString(),
      ingestLatencyMs,
      deliveryLagMs,
      groundingBasis: row.groundingBasis,
      groundingEvidence: row.groundingEvidence,
    };
  }

  private _dedupeAndSerialize(
    rows: YoutubePoiUpdate[],
    destinationMeta: { id: string | null; slug: string | null },
    safeLimit: number,
  ): YoutubeSerializedUpdateItem[] {
    const seenVideoIds = new Set<string>();
    const items: YoutubeSerializedUpdateItem[] = [];
    for (const row of rows) {
      if (seenVideoIds.has(row.videoId)) continue;
      seenVideoIds.add(row.videoId);
      items.push(this._serializeUpdateItem(row, destinationMeta));
      if (items.length >= safeLimit) break;
    }
    return items;
  }

  async listGroundedUpdatesForPlace(placeId: string, limit: number = 10) {
    const safeLimit = Math.min(Math.max(1, limit), 50);
    const place = await this.prisma.place.findUnique({
      where: { id: placeId },
      select: {
        id: true,
        name: true,
        deletedAt: true,
        destinationId: true,
        destination: {
          select: {
            id: true,
            slug: true,
            name: true,
          },
        },
        _count: { select: { placeSources: true } },
      },
    });
    if (!place || place.deletedAt || place._count.placeSources === 0) {
      throw new NotFoundException({
        message: `Verified place with ID "${placeId}" not found`,
        errorCode: YOUTUBE_ERROR_CODES.PLACE_NOT_FOUND,
      });
    }

    const destinationId = place.destination?.id ?? place.destinationId ?? null;
    const destinationMeta = {
      id: destinationId,
      slug: place.destination?.slug ?? null,
    };

    const [poiRows, cityRows] = await Promise.all([
      this.prisma.youtubePoiUpdate.findMany({
        where: {
          placeId,
          status: YoutubeUpdateStatus.LINKED,
          scope: YoutubeUpdateScope.POI,
        },
        orderBy: [
          { publishedAt: "desc" },
          { sourceUpdatedAt: "desc" },
          { receivedAt: "desc" },
        ],
        take: safeLimit * 3,
      }),
      destinationId
        ? this.prisma.youtubePoiUpdate.findMany({
            where: {
              destinationId,
              status: YoutubeUpdateStatus.LINKED_CITY,
              scope: YoutubeUpdateScope.CITY,
              placeId: null,
            },
            orderBy: [
              { publishedAt: "desc" },
              { sourceUpdatedAt: "desc" },
              { receivedAt: "desc" },
            ],
            take: safeLimit * 3,
          })
        : Promise.resolve([]),
    ]);

    const items = this._dedupeAndSerialize(poiRows, destinationMeta, safeLimit);
    const poiVideoIds = new Set(items.map((item) => item.videoId));
    const filteredCityRows = cityRows.filter(
      (row) => !poiVideoIds.has(row.videoId),
    );
    const cityFallbackItems = this._dedupeAndSerialize(
      filteredCityRows,
      destinationMeta,
      safeLimit,
    );

    return {
      placeId: place.id,
      placeName: place.name,
      destinationId,
      destinationSlug: place.destination?.slug ?? null,
      destinationName: place.destination?.name ?? null,
      governanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
      notPrimaryFactualCorpus: true,
      serverDeliveredAt: new Date().toISOString(),
      realtimeSlaMaxLatencyMs: this._getRealtimeSlaMaxLatencyMs(),
      total: items.length,
      items,
      cityFallbackTotal: cityFallbackItems.length,
      cityFallbackItems,
    };
  }

  async listGroundedUpdatesForDestination(
    idOrSlug: string,
    limit: number = 10,
    scopeFilter?: "POI" | "CITY",
  ) {
    const safeLimit = Math.min(Math.max(1, limit), 50);
    const trimmed = idOrSlug.trim();
    const isUuid = UUID_REGEX.test(trimmed);

    const destination = await this.prisma.destination.findUnique({
      where: isUuid ? { id: trimmed } : { slug: trimmed.toLowerCase() },
      select: {
        id: true,
        name: true,
        slug: true,
        deletedAt: true,
      },
    });

    if (!destination || destination.deletedAt) {
      throw new NotFoundException({
        message: `Destination "${idOrSlug}" not found`,
        errorCode: YOUTUBE_ERROR_CODES.DESTINATION_NOT_FOUND,
      });
    }

    const destinationMeta = {
      id: destination.id,
      slug: destination.slug,
    };

    const statusWhere: Prisma.YoutubePoiUpdateWhereInput["status"] =
      scopeFilter === "CITY"
        ? YoutubeUpdateStatus.LINKED_CITY
        : scopeFilter === "POI"
          ? YoutubeUpdateStatus.LINKED
          : {
              in: [
                YoutubeUpdateStatus.LINKED_CITY,
                YoutubeUpdateStatus.LINKED,
              ],
            };
    const scopeWhere: Prisma.YoutubePoiUpdateWhereInput["scope"] =
      scopeFilter === "CITY"
        ? YoutubeUpdateScope.CITY
        : scopeFilter === "POI"
          ? YoutubeUpdateScope.POI
          : {
              in: [YoutubeUpdateScope.CITY, YoutubeUpdateScope.POI],
            };

    const [itemRows, cityRows] = await Promise.all([
      this.prisma.youtubePoiUpdate.findMany({
        where: {
          destinationId: destination.id,
          status: statusWhere,
          scope: scopeWhere,
        },
        orderBy: [
          { publishedAt: "desc" },
          { sourceUpdatedAt: "desc" },
          { receivedAt: "desc" },
        ],
        take: safeLimit * 3,
      }),
      scopeFilter === "POI"
        ? Promise.resolve([])
        : this.prisma.youtubePoiUpdate.findMany({
            where: {
              destinationId: destination.id,
              status: YoutubeUpdateStatus.LINKED_CITY,
              scope: YoutubeUpdateScope.CITY,
              placeId: null,
            },
            orderBy: [
              { publishedAt: "desc" },
              { sourceUpdatedAt: "desc" },
              { receivedAt: "desc" },
            ],
            take: safeLimit * 3,
          }),
    ]);

    const consistentItemRows = itemRows.filter(
      (row) =>
        (row.status === YoutubeUpdateStatus.LINKED &&
          row.scope === YoutubeUpdateScope.POI) ||
        (row.status === YoutubeUpdateStatus.LINKED_CITY &&
          row.scope === YoutubeUpdateScope.CITY),
    );
    const items = this._dedupeAndSerialize(
      consistentItemRows,
      destinationMeta,
      safeLimit,
    );
    const poiVideoIds = new Set(
      consistentItemRows
        .filter(
          (row) =>
            row.status === YoutubeUpdateStatus.LINKED &&
            row.scope === YoutubeUpdateScope.POI,
        )
        .map((row) => row.videoId),
    );
    const filteredCityRows = cityRows.filter(
      (row) => !poiVideoIds.has(row.videoId),
    );
    const cityFallbackItems = this._dedupeAndSerialize(
      filteredCityRows,
      destinationMeta,
      safeLimit,
    );

    return {
      placeId: null,
      placeName: null,
      destinationId: destination.id,
      destinationSlug: destination.slug,
      destinationName: destination.name,
      governanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
      notPrimaryFactualCorpus: true,
      serverDeliveredAt: new Date().toISOString(),
      realtimeSlaMaxLatencyMs: this._getRealtimeSlaMaxLatencyMs(),
      total: items.length,
      items,
      cityFallbackTotal: cityFallbackItems.length,
      cityFallbackItems,
    };
  }
}
