import 'package:latlong2/latlong.dart';

/// Destination metadata served by `GET /destinations`.
///
/// The Map never hardcodes destination ids or coordinates: id, name and
/// coordinates always come from the backend. Only the *slugs* of the
/// supported MVP destinations are known to the app.
class DestinationModel {
  final String id;
  final String slug;
  final String name;
  final double? latitude;
  final double? longitude;

  const DestinationModel({
    required this.id,
    required this.slug,
    required this.name,
    this.latitude,
    this.longitude,
  });

  factory DestinationModel.fromJson(Map<String, dynamic> json) {
    double? num_(dynamic v) =>
        v == null ? null : double.tryParse(v.toString());
    return DestinationModel(
      id: (json['id'] ?? '').toString(),
      slug: (json['slug'] ?? '').toString(),
      name: (json['name'] ?? '').toString(),
      latitude: num_(json['latitude']),
      longitude: num_(json['longitude']),
    );
  }

  bool get hasValidCoordinates {
    final lat = latitude;
    final lon = longitude;
    return lat != null &&
        lon != null &&
        lat.isFinite &&
        lon.isFinite &&
        lat >= -90 &&
        lat <= 90 &&
        lon >= -180 &&
        lon <= 180;
  }

  LatLng get center => LatLng(latitude!, longitude!);
}

/// A supported MVP destination: hardcoded slug + display label only.
class SupportedDestination {
  final String slug;
  final String label;
  const SupportedDestination(this.slug, this.label);
}

/// Exactly the three MVP destinations the Map can browse.
const supportedDestinations = [
  SupportedDestination('ha-noi', 'Hà Nội'),
  SupportedDestination('da-nang', 'Đà Nẵng'),
  SupportedDestination('ha-long', 'Hạ Long'),
];

/// Thrown when the backend destination list cannot satisfy the Map contract.
class DestinationResolutionException implements Exception {
  final String message;
  const DestinationResolutionException(this.message);
  @override
  String toString() => message;
}

/// Resolves the supported slugs against the backend list. A missing,
/// duplicated or coordinate-less supported destination is an explicit error
/// (no silent fallback to hardcoded values).
Map<String, DestinationModel> resolveSupportedDestinations(
    List<DestinationModel> all) {
  final result = <String, DestinationModel>{};
  for (final s in supportedDestinations) {
    final matches = all.where((d) => d.slug == s.slug).toList();
    if (matches.isEmpty) {
      throw DestinationResolutionException(
          'Máy chủ chưa có điểm đến ${s.label} (${s.slug}).');
    }
    if (matches.length > 1) {
      throw DestinationResolutionException(
          'Điểm đến ${s.label} (${s.slug}) bị trùng trên máy chủ.');
    }
    final d = matches.single;
    if (d.id.isEmpty || !d.hasValidCoordinates) {
      throw DestinationResolutionException(
          'Điểm đến ${s.label} (${s.slug}) có dữ liệu tọa độ không hợp lệ.');
    }
    result[s.slug] = d;
  }
  return result;
}
