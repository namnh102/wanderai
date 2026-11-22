/// Place model for map display — reuses backend Place schema fields.
class PlaceModel {
  final String id;
  final String name;
  final String? nameEn;
  final String? description;
  final String? address;
  final double? latitude;
  final double? longitude;
  /// null = no rating available (never shown as 0 or a default).
  final double? rating;
  final int reviewCount;
  final String? coverImage;
  final List<String> images;
  final String? categoryName;
  final String? categoryIcon;
  final String? categoryColor;
  final String? destinationName;
  final bool isVerified;
  final int provenanceCount;
  final double? distanceKm;

  // Place Detail (TASK 08) & Wave C Enrichment — null/empty when unavailable.
  final String? openingHours;
  final String? website;
  final String? phone;
  final PlaceSourceInfo? source;
  final PlaceEnrichmentMeta? enrichmentMeta;
  final List<PlaceReviewModel> reviews;

  const PlaceModel({
    required this.id,
    required this.name,
    this.nameEn,
    this.description,
    this.address,
    this.latitude,
    this.longitude,
    this.rating,
    this.reviewCount = 0,
    this.coverImage,
    this.images = const [],
    this.categoryName,
    this.categoryIcon,
    this.categoryColor,
    this.destinationName,
    this.isVerified = false,
    this.provenanceCount = 0,
    this.distanceKm,
    this.openingHours,
    this.website,
    this.phone,
    this.source,
    this.enrichmentMeta,
    this.reviews = const [],
  });

  /// Parse from GET /places response item (Prisma-formatted with relations).
  factory PlaceModel.fromJson(Map<String, dynamic> json) {
    final category = json['category'] as Map<String, dynamic>?;
    final destination = json['destination'] as Map<String, dynamic>?;
    final rawImages = json['images'];
    final parsedImages = rawImages is List
        ? rawImages
            .whereType<String>()
            .map((e) => e.trim())
            .where((e) => e.isNotEmpty)
            .toList()
        : const <String>[];
    final rawReviews = json['reviews'];
    final parsedReviews = rawReviews is List
        ? rawReviews
            .whereType<Map<String, dynamic>>()
            .map(PlaceReviewModel.fromJson)
            .toList()
        : const <PlaceReviewModel>[];

    return PlaceModel(
      id: json['id'] as String,
      name: json['name'] as String,
      nameEn: json['nameEn'] as String?,
      description: _nonBlank(json['description']),
      address: json['address'] as String?,
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      rating: (json['rating'] as num?)?.toDouble(),
      reviewCount: (json['reviewCount'] as num?)?.toInt() ??
          (json['_count'] != null
              ? ((json['_count'] as Map)['reviews'] as num?)?.toInt() ?? 0
              : 0),
      coverImage: _nonBlank(json['coverImage'] ?? json['cover_image']),
      images: parsedImages,
      categoryName: category?['name'] as String? ??
          json['categoryName'] as String?,
      categoryIcon: category?['icon'] as String?,
      categoryColor: category?['color'] as String?,
      destinationName: destination?['name'] as String? ??
          json['destinationName'] as String?,
      isVerified: json['isVerified'] as bool? ?? false,
      provenanceCount: (json['provenanceCount'] as num?)?.toInt() ?? 0,
      distanceKm: (json['distanceKm'] as num?)?.toDouble(),
      openingHours: _nonBlank(json['openingHours']),
      website: _nonBlank(json['website']),
      phone: _nonBlank(json['phone']),
      source: json['source'] is Map<String, dynamic>
          ? PlaceSourceInfo.fromJson(json['source'] as Map<String, dynamic>)
          : null,
      enrichmentMeta: json['enrichmentMeta'] is Map<String, dynamic>
          ? PlaceEnrichmentMeta.fromJson(
              json['enrichmentMeta'] as Map<String, dynamic>)
          : null,
      reviews: parsedReviews,
    );
  }

  static String? _nonBlank(dynamic v) {
    if (v is! String) return null;
    final t = v.trim();
    return t.isEmpty ? null : t;
  }

  bool get hasCoordinates => latitude != null && longitude != null;

  /// Exact text shown when the API has no factual (OSM-backed) address.
  static const addressUnavailableText = 'Chưa có thông tin địa chỉ.';

  /// True only when the API returned a real, non-blank address.
  bool get hasAddress => address != null && address!.trim().isNotEmpty;

  /// Address exactly as served by the API, or the honest unavailable text.
  /// Never composed from name/destination — shared by preview sheet and detail screen.
  String get addressDisplay => hasAddress ? address!.trim() : addressUnavailableText;
}

/// Provenance of a place (OpenStreetMap). Only present for verified places.
class PlaceSourceInfo {
  final String name;
  final String sourceId;
  final String canonicalUrl;
  final String? license;
  final String? attribution;

  const PlaceSourceInfo({
    required this.name,
    required this.sourceId,
    required this.canonicalUrl,
    this.license,
    this.attribution,
  });

  factory PlaceSourceInfo.fromJson(Map<String, dynamic> json) {
    return PlaceSourceInfo(
      name: json['name'] as String? ?? 'OpenStreetMap',
      sourceId: json['sourceId'] as String? ?? '',
      canonicalUrl: json['canonicalUrl'] as String? ?? '',
      license: json['license'] as String?,
      attribution: json['attribution'] as String?,
    );
  }
}

/// Optional license & attribution metadata for curated Wikimedia/Wikipedia enrichment.
class PlaceEnrichmentMeta {
  final String? descriptionSourceUrl;
  final String? descriptionLicense;
  final String? firstImageLicense;
  final String? firstImageArtist;

  const PlaceEnrichmentMeta({
    this.descriptionSourceUrl,
    this.descriptionLicense,
    this.firstImageLicense,
    this.firstImageArtist,
  });

  factory PlaceEnrichmentMeta.fromJson(Map<String, dynamic> json) {
    final attrs = json['imageAttributions'];
    Map<String, dynamic>? firstAttr;
    if (attrs is List && attrs.isNotEmpty && attrs.first is Map) {
      firstAttr = Map<String, dynamic>.from(attrs.first as Map);
    }
    return PlaceEnrichmentMeta(
      descriptionSourceUrl: json['descriptionSourceUrl'] as String?,
      descriptionLicense: json['descriptionLicense'] as String?,
      firstImageLicense: firstAttr?['license'] as String?,
      firstImageArtist: firstAttr?['artist'] as String?,
    );
  }
}

/// Verified traveler review parsed from public `GET /places/:id` or `/reviews`.
class PlaceReviewModel {
  final String id;
  final double rating;
  final String content;
  final String authorName;
  final DateTime? createdAt;

  const PlaceReviewModel({
    required this.id,
    required this.rating,
    required this.content,
    required this.authorName,
    this.createdAt,
  });

  factory PlaceReviewModel.fromJson(Map<String, dynamic> json) {
    final user = json['user'] as Map<String, dynamic>?;
    final profile = user?['profile'] as Map<String, dynamic>?;
    final rawName = (profile?['displayName'] as String?)?.trim();
    return PlaceReviewModel(
      id: json['id'] as String? ?? '',
      rating: (json['rating'] as num?)?.toDouble() ?? 0.0,
      content: json['content'] as String? ?? '',
      authorName:
          (rawName != null && rawName.isNotEmpty) ? rawName : 'Du khách GoMate',
      createdAt: json['createdAt'] is String
          ? DateTime.tryParse(json['createdAt'] as String)
          : null,
    );
  }
}
