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
  final String? categoryName;
  final String? categoryIcon;
  final String? categoryColor;
  final String? destinationName;
  final bool isVerified;
  final int provenanceCount;
  final double? distanceKm;

  // Place Detail (TASK 08) — all null when the backend has no factual data.
  final String? openingHours;
  final String? website;
  final String? phone;
  final PlaceSourceInfo? source;

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
  });

  /// Parse from GET /places response item (Prisma-formatted with relations).
  factory PlaceModel.fromJson(Map<String, dynamic> json) {
    final category = json['category'] as Map<String, dynamic>?;
    final destination = json['destination'] as Map<String, dynamic>?;

    return PlaceModel(
      id: json['id'] as String,
      name: json['name'] as String,
      nameEn: json['nameEn'] as String?,
      description: json['description'] as String?,
      address: json['address'] as String?,
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      rating: (json['rating'] as num?)?.toDouble(),
      reviewCount: (json['reviewCount'] as num?)?.toInt() ??
          (json['_count'] != null
              ? ((json['_count'] as Map)['reviews'] as num?)?.toInt() ?? 0
              : 0),
      coverImage: json['coverImage'] ?? json['cover_image'] as String?,
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
