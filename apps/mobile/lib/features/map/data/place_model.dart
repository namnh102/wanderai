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
    );
  }

  bool get hasCoordinates => latitude != null && longitude != null;
}
