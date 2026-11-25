import 'dart:math' as math;

/// Grounding scope returned by `GET /places/:id/youtube-updates` and
/// `GET /destinations/:idOrSlug/youtube-updates`.
enum YoutubeUpdateScope {
  poi,
  city,
  none;

  static YoutubeUpdateScope fromJson(String? raw) {
    switch (raw?.trim().toUpperCase()) {
      case 'POI':
        return YoutubeUpdateScope.poi;
      case 'CITY':
        return YoutubeUpdateScope.city;
      default:
        return YoutubeUpdateScope.none;
    }
  }

  String get apiValue {
    switch (this) {
      case YoutubeUpdateScope.poi:
        return 'POI';
      case YoutubeUpdateScope.city:
        return 'CITY';
      case YoutubeUpdateScope.none:
        return 'NONE';
    }
  }
}

DateTime? _tryParseDateTime(dynamic raw) {
  if (raw is DateTime) return raw.toUtc();
  if (raw is String && raw.trim().isNotEmpty) {
    return DateTime.tryParse(raw.trim())?.toUtc();
  }
  return null;
}

String? _nullableTrimmedString(dynamic raw) {
  if (raw is! String) return null;
  final trimmed = raw.trim();
  return trimmed.isEmpty ? null : trimmed;
}

/// Single YouTube social-freshness item in `DYNAMIC_SOCIAL_FRESHNESS_LAYER`.
/// Strictly preserves the 5 mandated contract fields:
/// `placeId`, `source`, `publishedAt`, `receivedAt`, `updatedAt`.
class YoutubeUpdateModel {
  final String id;
  final String? placeId;
  final String? destinationId;
  final String? destinationSlug;
  final YoutubeUpdateScope scope;
  final String source;
  final String channelId;
  final String? channelTitle;
  final String videoId;
  final String videoUrl;
  final String title;
  final String? description;
  final List<String> tags;
  final DateTime publishedAt;
  final DateTime receivedAt;
  final DateTime updatedAt;
  final DateTime? sourceUpdatedAt;
  final DateTime? lastReceivedAt;
  final int ingestLatencyMs;
  final int deliveryLagMs;
  final String? groundingBasis;
  final Map<String, dynamic>? groundingEvidence;

  const YoutubeUpdateModel({
    required this.id,
    required this.placeId,
    required this.destinationId,
    required this.destinationSlug,
    required this.scope,
    required this.source,
    required this.channelId,
    required this.channelTitle,
    required this.videoId,
    required this.videoUrl,
    required this.title,
    required this.description,
    required this.tags,
    required this.publishedAt,
    required this.receivedAt,
    required this.updatedAt,
    required this.sourceUpdatedAt,
    required this.lastReceivedAt,
    required this.ingestLatencyMs,
    required this.deliveryLagMs,
    required this.groundingBasis,
    required this.groundingEvidence,
  });

  bool get isCityLevel => scope == YoutubeUpdateScope.city && placeId == null;

  /// Measures source-to-app latency (ms) against [clientRenderedAt].
  int endToEndLatencyMsAt(DateTime clientRenderedAt) {
    return clientRenderedAt.toUtc().difference(publishedAt.toUtc()).inMilliseconds;
  }

  /// `"Thời gian thực"` is allowed ONLY when measured source-to-app latency is
  /// non-negative and within [slaMaxLatencyMs] (default 300,000 ms / 5 min).
  bool isRealtimeAt(
    DateTime clientRenderedAt, {
    int slaMaxLatencyMs = 300000,
  }) {
    final lag = endToEndLatencyMsAt(clientRenderedAt);
    return lag >= 0 && lag <= slaMaxLatencyMs;
  }

  String freshnessBadgeLabelAt(
    DateTime clientRenderedAt, {
    int slaMaxLatencyMs = 300000,
  }) {
    return isRealtimeAt(clientRenderedAt, slaMaxLatencyMs: slaMaxLatencyMs)
        ? 'Thời gian thực'
        : 'Cập nhật gần đây';
  }

  factory YoutubeUpdateModel.fromJson(Map<String, dynamic> json) {
    final epochFallback = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
    final receivedAt = _tryParseDateTime(json['receivedAt']) ?? epochFallback;
    final publishedAt =
        _tryParseDateTime(json['publishedAt']) ?? receivedAt;
    final sourceUpdatedAt = _tryParseDateTime(json['sourceUpdatedAt']);
    final lastReceivedAt = _tryParseDateTime(json['lastReceivedAt']);
    final updatedAt = _tryParseDateTime(json['updatedAt']) ??
        sourceUpdatedAt ??
        lastReceivedAt ??
        receivedAt;

    final scope = YoutubeUpdateScope.fromJson(json['scope'] as String?);
    final rawPlaceId = _nullableTrimmedString(json['placeId']);
    final placeId = scope == YoutubeUpdateScope.city ? null : rawPlaceId;

    final rawVideoId = (json['videoId'] as String? ?? '').trim();
    final rawVideoUrl = _nullableTrimmedString(json['videoUrl']);
    final videoUrl = rawVideoUrl ??
        (rawVideoId.isNotEmpty
            ? 'https://www.youtube.com/watch?v=$rawVideoId'
            : '');

    final rawTags = json['tags'];
    final tags = rawTags is List
        ? rawTags
            .whereType<String>()
            .map((t) => t.trim())
            .where((t) => t.isNotEmpty)
            .toList()
        : const <String>[];

    final rawEvidence = json['groundingEvidence'];
    final groundingEvidence = rawEvidence is Map
        ? Map<String, dynamic>.from(rawEvidence)
        : null;

    final computedIngestLatency = math.max(
      0,
      receivedAt.difference(publishedAt).inMilliseconds,
    );
    final computedDeliveryLag = math.max(
      0,
      (lastReceivedAt ?? receivedAt).difference(publishedAt).inMilliseconds,
    );

    return YoutubeUpdateModel(
      id: (json['id'] as String? ?? rawVideoId).trim(),
      placeId: placeId,
      destinationId: _nullableTrimmedString(json['destinationId']),
      destinationSlug: _nullableTrimmedString(json['destinationSlug']),
      scope: scope,
      source: _nullableTrimmedString(json['source']) ?? 'youtube',
      channelId: (json['channelId'] as String? ?? '').trim(),
      channelTitle: _nullableTrimmedString(json['channelTitle']),
      videoId: rawVideoId,
      videoUrl: videoUrl,
      title: _nullableTrimmedString(json['title']) ?? 'Cập nhật YouTube',
      description: _nullableTrimmedString(json['description']),
      tags: tags,
      publishedAt: publishedAt,
      receivedAt: receivedAt,
      updatedAt: updatedAt,
      sourceUpdatedAt: sourceUpdatedAt,
      lastReceivedAt: lastReceivedAt,
      ingestLatencyMs:
          (json['ingestLatencyMs'] as num?)?.toInt() ?? computedIngestLatency,
      deliveryLagMs:
          (json['deliveryLagMs'] as num?)?.toInt() ?? computedDeliveryLag,
      groundingBasis: _nullableTrimmedString(json['groundingBasis']),
      groundingEvidence: groundingEvidence,
    );
  }
}

/// Envelope returned by `/places/:id/youtube-updates` and
/// `/destinations/:idOrSlug/youtube-updates`.
class YoutubeUpdatesEnvelope {
  static const defaultGovernanceRole = 'DYNAMIC_SOCIAL_FRESHNESS_LAYER';
  static const defaultSlaMaxLatencyMs = 300000;

  final String? placeId;
  final String? placeName;
  final String? destinationId;
  final String? destinationSlug;
  final String? destinationName;
  final String governanceRole;
  final bool notPrimaryFactualCorpus;
  final DateTime serverDeliveredAt;
  final int realtimeSlaMaxLatencyMs;
  final int total;
  final List<YoutubeUpdateModel> items;
  final int cityFallbackTotal;
  final List<YoutubeUpdateModel> cityFallbackItems;

  const YoutubeUpdatesEnvelope({
    this.placeId,
    this.placeName,
    this.destinationId,
    this.destinationSlug,
    this.destinationName,
    this.governanceRole = defaultGovernanceRole,
    this.notPrimaryFactualCorpus = true,
    required this.serverDeliveredAt,
    this.realtimeSlaMaxLatencyMs = defaultSlaMaxLatencyMs,
    required this.total,
    required this.items,
    this.cityFallbackTotal = 0,
    this.cityFallbackItems = const [],
  });

  YoutubeUpdatesEnvelope copyWith({
    int? total,
    List<YoutubeUpdateModel>? items,
    int? cityFallbackTotal,
    List<YoutubeUpdateModel>? cityFallbackItems,
  }) {
    return YoutubeUpdatesEnvelope(
      placeId: placeId,
      placeName: placeName,
      destinationId: destinationId,
      destinationSlug: destinationSlug,
      destinationName: destinationName,
      governanceRole: governanceRole,
      notPrimaryFactualCorpus: notPrimaryFactualCorpus,
      serverDeliveredAt: serverDeliveredAt,
      realtimeSlaMaxLatencyMs: realtimeSlaMaxLatencyMs,
      total: total ?? this.total,
      items: items ?? this.items,
      cityFallbackTotal: cityFallbackTotal ?? this.cityFallbackTotal,
      cityFallbackItems: cityFallbackItems ?? this.cityFallbackItems,
    );
  }

  factory YoutubeUpdatesEnvelope.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'];
    final items = rawItems is List
        ? rawItems
            .whereType<Map>()
            .map((m) => YoutubeUpdateModel.fromJson(Map<String, dynamic>.from(m)))
            .toList()
        : const <YoutubeUpdateModel>[];

    final rawFallback = json['cityFallbackItems'];
    final cityFallbackItems = rawFallback is List
        ? rawFallback
            .whereType<Map>()
            .map((m) => YoutubeUpdateModel.fromJson(Map<String, dynamic>.from(m)))
            .toList()
        : const <YoutubeUpdateModel>[];

    final rawSla = (json['realtimeSlaMaxLatencyMs'] as num?)?.toInt();
    final slaMax =
        (rawSla != null && rawSla > 0) ? rawSla : defaultSlaMaxLatencyMs;

    return YoutubeUpdatesEnvelope(
      placeId: _nullableTrimmedString(json['placeId']),
      placeName: _nullableTrimmedString(json['placeName']),
      destinationId: _nullableTrimmedString(json['destinationId']),
      destinationSlug: _nullableTrimmedString(json['destinationSlug']),
      destinationName: _nullableTrimmedString(json['destinationName']),
      governanceRole:
          _nullableTrimmedString(json['governanceRole']) ?? defaultGovernanceRole,
      notPrimaryFactualCorpus: json['notPrimaryFactualCorpus'] as bool? ?? true,
      serverDeliveredAt: _tryParseDateTime(json['serverDeliveredAt']) ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
      realtimeSlaMaxLatencyMs: slaMax,
      total: (json['total'] as num?)?.toInt() ?? items.length,
      items: items,
      cityFallbackTotal:
          (json['cityFallbackTotal'] as num?)?.toInt() ?? cityFallbackItems.length,
      cityFallbackItems: cityFallbackItems,
    );
  }
}
