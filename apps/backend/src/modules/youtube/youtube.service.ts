import {
  BadRequestException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from "@nestjs/common";
import { ConfigService } from "@nestjs/config";
import { Prisma, YoutubePoiUpdate, YoutubeUpdateStatus } from "@prisma/client";
import * as fs from "fs";
import * as path from "path";
import { PrismaService } from "../../prisma/prisma.service";
import { osmAddress } from "../places/osm-tags";
import { IngestYoutubeEventDto } from "./dto/youtube-update.dto";
import {
  computeYoutubeDedupeKey,
  evaluatePoiGrounding,
  extractVerifiedAliasesFromDescription,
  NormalizedYoutubeEventInput,
  parseYoutubeAtomFeed,
  VerifiedPlaceCandidate,
  verifyWebSubSignature,
} from "./youtube-grounding";

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
  linkedPlaceId: string | null;
  groundingBasis: string | null;
  decisionReason: string;
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
      throw new ForbiddenException("Invalid hub.verify_token");
    }

    return challenge;
  }

  async ingestAtomWebhook(
    rawXml: string,
    signatureHeader?: string,
  ): Promise<{ processedCount: number; results: YoutubeIngestionReceipt[] }> {
    const secret = this.configService.get<string>("YOUTUBE_WEBSUB_SECRET");
    verifyWebSubSignature(rawXml, signatureHeader, secret);

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
        name: true,
        nameEn: true,
        description: true,
        latitude: true,
        longitude: true,
        destination: {
          select: {
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

  private async _recordDuplicateDelivery(
    dedupeKey: string,
    now: Date,
  ): Promise<YoutubePoiUpdate> {
    return this.prisma.youtubePoiUpdate.update({
      where: { dedupeKey },
      data: {
        deliveryCount: { increment: 1 },
        lastReceivedAt: now,
      },
    });
  }

  private _toReceipt(
    row: YoutubePoiUpdate,
    duplicate: boolean,
  ): YoutubeIngestionReceipt {
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
      linkedPlaceId: row.placeId,
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
      const updated = await this._recordDuplicateDelivery(
        dedupeKey,
        receivedAt,
      );
      return this._toReceipt(updated, true);
    }

    const candidates = await this._loadVerifiedPlaceCandidates();
    const decision = evaluatePoiGrounding(event, candidates);
    const canonicalVideoUrl = `https://www.youtube.com/watch?v=${event.videoId}`;

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
          status:
            decision.status === "LINKED"
              ? YoutubeUpdateStatus.LINKED
              : YoutubeUpdateStatus.UNLINKED_NO_BASIS,
          placeId: decision.placeId,
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
        const updated = await this._recordDuplicateDelivery(
          dedupeKey,
          receivedAt,
        );
        return this._toReceipt(updated, true);
      }
      throw err;
    }
  }

  async listGroundedUpdatesForPlace(placeId: string, limit: number = 10) {
    const safeLimit = Math.min(Math.max(1, limit), 50);
    const place = await this.prisma.place.findUnique({
      where: { id: placeId },
      select: {
        id: true,
        name: true,
        deletedAt: true,
        _count: { select: { placeSources: true } },
      },
    });
    if (!place || place.deletedAt || place._count.placeSources === 0) {
      throw new NotFoundException(
        `Verified place with ID "${placeId}" not found`,
      );
    }

    const rows = await this.prisma.youtubePoiUpdate.findMany({
      where: {
        placeId,
        status: YoutubeUpdateStatus.LINKED,
      },
      orderBy: [
        { publishedAt: "desc" },
        { sourceUpdatedAt: "desc" },
        { receivedAt: "desc" },
      ],
      take: safeLimit * 3,
    });

    // Deduplicate revisions by videoId while keeping latest revision per video
    const seenVideoIds = new Set<string>();
    const items = [];
    for (const row of rows) {
      if (seenVideoIds.has(row.videoId)) continue;
      seenVideoIds.add(row.videoId);
      items.push({
        id: row.id,
        videoId: row.videoId,
        videoUrl: row.videoUrl,
        channelId: row.channelId,
        channelTitle: row.channelTitle,
        title: row.title,
        description: row.description,
        tags: row.tags,
        publishedAt: row.publishedAt.toISOString(),
        receivedAt: row.receivedAt.toISOString(),
        groundingBasis: row.groundingBasis,
        groundingEvidence: row.groundingEvidence,
      });
      if (items.length >= safeLimit) break;
    }

    return {
      placeId: place.id,
      placeName: place.name,
      governanceRole: "DYNAMIC_SOCIAL_FRESHNESS_LAYER",
      notPrimaryFactualCorpus: true,
      total: items.length,
      items,
    };
  }
}
