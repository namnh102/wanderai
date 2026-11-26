import 'dart:math' as math;
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'destination_model.dart';
import 'place_model.dart';

/// Reference Freeze V2 Hạ Long POI IDs enclosed by [halongOfflineRegionPreset].
const halongThapDongHoId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
const halongBaoTangQuangNinhId = '8f2b5a69-1293-4efe-8fc5-3a74193edd0f';

/// Axis-aligned WGS-84 bounding box for an offline map region.
class OfflineBoundingBox {
  final double south;
  final double west;
  final double north;
  final double east;

  const OfflineBoundingBox({
    required this.south,
    required this.west,
    required this.north,
    required this.east,
  });

  factory OfflineBoundingBox.fromJson(Map<String, dynamic> json) {
    return OfflineBoundingBox(
      south: (json['south'] as num).toDouble(),
      west: (json['west'] as num).toDouble(),
      north: (json['north'] as num).toDouble(),
      east: (json['east'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'south': south,
        'west': west,
        'north': north,
        'east': east,
      };

  LatLng get center => LatLng((south + north) / 2.0, (west + east) / 2.0);

  LatLngBounds toLatLngBounds() =>
      LatLngBounds(LatLng(south, west), LatLng(north, east));

  bool contains(LatLng point) =>
      point.latitude >= south &&
      point.latitude <= north &&
      point.longitude >= west &&
      point.longitude <= east;

  List<LatLng> get polygonPoints => [
        LatLng(south, west),
        LatLng(north, west),
        LatLng(north, east),
        LatLng(south, east),
      ];

  String get formattedLabel =>
      '${south.toStringAsFixed(3)}–${north.toStringAsFixed(3)}°N, '
      '${west.toStringAsFixed(3)}–${east.toStringAsFixed(3)}°E';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is OfflineBoundingBox &&
          south == other.south &&
          west == other.west &&
          north == other.north &&
          east == other.east);

  @override
  int get hashCode => Object.hash(south, west, north, east);
}

/// Static configuration preset for an offline map region download.
class OfflineRegionPreset {
  final String regionId;
  final String destinationSlug;
  final String name;
  final OfflineBoundingBox bounds;
  final int minZoom;
  final int maxZoom;
  final double recommendedInitialZoom;

  const OfflineRegionPreset({
    required this.regionId,
    required this.destinationSlug,
    required this.name,
    required this.bounds,
    required this.minZoom,
    required this.maxZoom,
    required this.recommendedInitialZoom,
  });
}

/// Compact Hạ Long test region enclosing Tháp Đồng Hồ & Bảo tàng Quảng Ninh
/// (112 tiles total across zoom levels z12..z17).
const halongOfflineRegionPreset = OfflineRegionPreset(
  regionId: 'ha-long',
  destinationSlug: 'ha-long',
  name: 'Hạ Long (Tháp Đồng Hồ – Bảo tàng Quảng Ninh)',
  bounds: OfflineBoundingBox(
    south: 20.942,
    west: 107.078,
    north: 20.958,
    east: 107.105,
  ),
  minZoom: 12,
  maxZoom: 17,
  recommendedInitialZoom: 15.0,
);

/// Slippy-map XYZ tile coordinate.
class OfflineTileCoord {
  final int z;
  final int x;
  final int y;

  const OfflineTileCoord(this.z, this.x, this.y);

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is OfflineTileCoord && z == other.z && x == other.x && y == other.y);

  @override
  int get hashCode => Object.hash(z, x, y);

  @override
  String toString() => 'Tile($z/$x/$y)';
}

/// Converts WGS-84 longitude (degrees) to slippy-map tile X at zoom [z].
int lonToTileX(double lon, int z) {
  final n = 1 << z;
  final raw = ((lon + 180.0) / 360.0 * n).floor();
  return raw.clamp(0, n - 1);
}

/// Converts WGS-84 latitude (degrees) to slippy-map tile Y at zoom [z].
int latToTileY(double lat, int z) {
  final n = 1 << z;
  final clampedLat = lat.clamp(-85.05112878, 85.05112878);
  final latRad = clampedLat * math.pi / 180.0;
  final mercN = math.log(math.tan(latRad) + 1.0 / math.cos(latRad));
  final raw = ((1.0 - mercN / math.pi) / 2.0 * n).floor();
  return raw.clamp(0, n - 1);
}

/// Enumerates all unique Web Mercator XYZ tiles intersecting [bbox] for
/// `[minZoom .. maxZoom]` inclusive.
List<OfflineTileCoord> enumerateTilesForBounds(
  OfflineBoundingBox bbox,
  int minZoom,
  int maxZoom,
) {
  if (minZoom > maxZoom) return const [];
  final tiles = <OfflineTileCoord>[];
  for (var z = minZoom; z <= maxZoom; z++) {
    final xMin = lonToTileX(bbox.west, z);
    final xMax = lonToTileX(bbox.east, z);
    final yMin = latToTileY(bbox.north, z);
    final yMax = latToTileY(bbox.south, z);
    for (var x = xMin; x <= xMax; x++) {
      for (var y = yMin; y <= yMax; y++) {
        tiles.add(OfflineTileCoord(z, x, y));
      }
    }
  }
  return tiles;
}

/// Persisted manifest (`manifest.json`) describing a downloaded offline region,
/// its measured disk usage, and cached destination/POI metadata.
class OfflineRegionManifest {
  final String regionId;
  final String destinationSlug;
  final String name;
  final OfflineBoundingBox bbox;
  final int minZoom;
  final int maxZoom;
  final double recommendedInitialZoom;
  final int tileCount;
  final int expectedTileCount;
  final int downloadedBytes;
  final DateTime downloadedAt;
  final String sourceTemplate;
  final String? fallbackTemplate;
  final DestinationModel? destination;
  final List<PlaceModel> places;

  const OfflineRegionManifest({
    required this.regionId,
    required this.destinationSlug,
    required this.name,
    required this.bbox,
    required this.minZoom,
    required this.maxZoom,
    required this.recommendedInitialZoom,
    required this.tileCount,
    required this.expectedTileCount,
    required this.downloadedBytes,
    required this.downloadedAt,
    required this.sourceTemplate,
    this.fallbackTemplate,
    this.destination,
    this.places = const [],
  });

  bool get isComplete => expectedTileCount > 0 && tileCount >= expectedTileCount;

  double get downloadedMegabytes => downloadedBytes / (1024 * 1024);

  String get formattedSize {
    if (downloadedBytes >= 1024 * 1024) {
      return '${downloadedMegabytes.toStringAsFixed(2)} MB ($downloadedBytes bytes)';
    }
    if (downloadedBytes >= 1024) {
      return '${(downloadedBytes / 1024).toStringAsFixed(1)} KB ($downloadedBytes bytes)';
    }
    return '$downloadedBytes bytes';
  }

  bool containsZoom(double zoom) =>
      zoom >= minZoom - 0.05 && zoom <= maxZoom + 0.05;

  Map<String, dynamic> toJson() => {
        'regionId': regionId,
        'destinationSlug': destinationSlug,
        'name': name,
        'bbox': bbox.toJson(),
        'minZoom': minZoom,
        'maxZoom': maxZoom,
        'recommendedInitialZoom': recommendedInitialZoom,
        'tileCount': tileCount,
        'expectedTileCount': expectedTileCount,
        'downloadedBytes': downloadedBytes,
        'downloadedAt': downloadedAt.toUtc().toIso8601String(),
        'sourceTemplate': sourceTemplate,
        if (fallbackTemplate != null) 'fallbackTemplate': fallbackTemplate,
        if (destination != null) 'destination': destination!.toJson(),
        'places': places.map((p) => p.toJson()).toList(),
      };

  factory OfflineRegionManifest.fromJson(Map<String, dynamic> json) {
    final rawPlaces = json['places'];
    final parsedPlaces = rawPlaces is List
        ? rawPlaces
            .whereType<Map>()
            .map((e) => PlaceModel.fromJson(Map<String, dynamic>.from(e)))
            .toList()
        : const <PlaceModel>[];
    final rawDest = json['destination'];
    return OfflineRegionManifest(
      regionId: (json['regionId'] ?? 'ha-long').toString(),
      destinationSlug: (json['destinationSlug'] ?? 'ha-long').toString(),
      name: (json['name'] ?? '').toString(),
      bbox: OfflineBoundingBox.fromJson(
        Map<String, dynamic>.from(json['bbox'] as Map),
      ),
      minZoom: (json['minZoom'] as num).toInt(),
      maxZoom: (json['maxZoom'] as num).toInt(),
      recommendedInitialZoom:
          (json['recommendedInitialZoom'] as num?)?.toDouble() ?? 15.0,
      tileCount: (json['tileCount'] as num?)?.toInt() ?? 0,
      expectedTileCount: (json['expectedTileCount'] as num?)?.toInt() ?? 0,
      downloadedBytes: (json['downloadedBytes'] as num?)?.toInt() ?? 0,
      downloadedAt: DateTime.tryParse(json['downloadedAt']?.toString() ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
      sourceTemplate: (json['sourceTemplate'] ?? '').toString(),
      fallbackTemplate: json['fallbackTemplate']?.toString(),
      destination: rawDest is Map
          ? DestinationModel.fromJson(Map<String, dynamic>.from(rawDest))
          : null,
      places: parsedPlaces,
    );
  }
}

/// Progress snapshot emitted while downloading an offline region.
class OfflineDownloadProgress {
  final int completedTiles;
  final int totalTiles;
  final int downloadedBytes;
  final int failedTiles;
  final int skippedTiles;
  final bool isCompleted;
  final bool isCancelled;

  const OfflineDownloadProgress({
    required this.completedTiles,
    required this.totalTiles,
    required this.downloadedBytes,
    this.failedTiles = 0,
    this.skippedTiles = 0,
    this.isCompleted = false,
    this.isCancelled = false,
  });

  double get fraction =>
      totalTiles <= 0 ? 0.0 : (completedTiles / totalTiles).clamp(0.0, 1.0);
}
