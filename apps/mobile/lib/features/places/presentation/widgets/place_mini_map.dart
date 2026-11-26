import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../map/data/cached_offline_tile_provider.dart';
import '../../../map/data/offline_tile_downloader.dart';
import '../../../map/data/place_model.dart';
import '../../../map/providers/map_provider.dart';

/// Non-interactive mini map showing a single place from its stored coordinates.
/// Same OSM HOT tiles as the main map (ADR-006) with disk offline tile cache
/// and visible attribution.
class PlaceMiniMap extends ConsumerWidget {
  final PlaceModel place;
  final double height;
  final TileProvider? tileProvider;

  const PlaceMiniMap({
    super.key,
    required this.place,
    this.height = 180,
    this.tileProvider,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final point = LatLng(place.latitude!, place.longitude!);
    final color = AppColors.forCategory(place.categoryName);
    final resolvedTileProvider = tileProvider ??
        CachedOfflineTileProvider(
          store: ref.watch(offlineTileStoreProvider),
          dio: ref.watch(offlineTileDioProvider),
          isOfflineOnly: () => ref.read(mapProvider).isOfflineMode,
        );

    return ClipRRect(
      borderRadius: AppRadius.mdRadius,
      child: SizedBox(
        height: height,
        child: FlutterMap(
          options: MapOptions(
            initialCenter: point,
            initialZoom: 16,
            interactionOptions:
                const InteractionOptions(flags: InteractiveFlag.none),
          ),
          children: [
            TileLayer(
              urlTemplate: OfflineTileDownloader.primaryUrlTemplate,
              fallbackUrl: OfflineTileDownloader.fallbackUrlTemplate,
              subdomains: OfflineTileDownloader.subdomains,
              userAgentPackageName: 'com.wanderai.mobile',
              maxZoom: 19,
              tileProvider: resolvedTileProvider,
              evictErrorTileStrategy:
                  EvictErrorTileStrategy.notVisibleRespectMargin,
              errorImage: MemoryImage(TileProvider.transparentImage),
            ),
            MarkerLayer(
              markers: [
                Marker(
                  point: point,
                  width: 40,
                  height: 40,
                  child: Icon(Icons.location_on, color: color, size: 40),
                ),
              ],
            ),
            const RichAttributionWidget(
              alignment: AttributionAlignment.bottomLeft,
              attributions: [
                TextSourceAttribution('OpenStreetMap contributors'),
                TextSourceAttribution(
                    'Tiles: Humanitarian OpenStreetMap Team / OSM France'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
