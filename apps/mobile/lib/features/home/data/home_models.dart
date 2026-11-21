import '../../profile/data/profile_models.dart';

/// Region filter values supported by `GET /destinations`.
enum HomeRegionFilter {
  all(null, 'Tất cả'),
  north('north', 'Miền Bắc'),
  central('central', 'Miền Trung'),
  south('south', 'Miền Nam');

  final String? apiValue;
  final String label;

  const HomeRegionFilter(this.apiValue, this.label);
}

/// Typed destination item parsed from `GET /destinations`.
class HomeDestinationItem {
  final String id;
  final String name;
  final String? nameEn;
  final String slug;
  final String province;
  final String? region;
  final String? description;
  final double? latitude;
  final double? longitude;
  /// `null` unless backed by real traveler reviews (`destination-trust.ts`).
  final double? rating;
  final int reviewCount;
  final bool isPopular;
  final int placeCount;

  const HomeDestinationItem({
    required this.id,
    required this.name,
    this.nameEn,
    required this.slug,
    required this.province,
    this.region,
    this.description,
    this.latitude,
    this.longitude,
    this.rating,
    this.reviewCount = 0,
    this.isPopular = false,
    this.placeCount = 0,
  });

  factory HomeDestinationItem.fromJson(Map<String, dynamic> json) {
    final count = json['_count'];
    final placesCount =
        count is Map ? ((count['places'] as num?)?.toInt() ?? 0) : 0;
    return HomeDestinationItem(
      id: (json['id'] ?? '').toString(),
      name: (json['name'] ?? '').toString(),
      nameEn: json['nameEn'] as String?,
      slug: (json['slug'] ?? '').toString(),
      province: (json['province'] ?? '').toString(),
      region: json['region'] as String?,
      description: json['description'] as String?,
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      rating: (json['rating'] as num?)?.toDouble(),
      reviewCount: (json['reviewCount'] as num?)?.toInt() ?? 0,
      isPopular: json['isPopular'] == true,
      placeCount: placesCount,
    );
  }

  String get regionLabel {
    switch (region?.toLowerCase()) {
      case 'north':
        return 'Miền Bắc';
      case 'central':
        return 'Miền Trung';
      case 'south':
        return 'Miền Nam';
      default:
        return 'Việt Nam';
    }
  }
}

/// Human-readable interest labels matching backend canonical keys.
String interestDisplayLabel(String key) {
  for (final item in kCanonicalInterests) {
    if (item.key == key) return item.label;
  }
  return key;
}
