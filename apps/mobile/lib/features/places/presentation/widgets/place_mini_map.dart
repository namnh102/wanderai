import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../map/data/place_model.dart';

/// Non-interactive mini map showing a single place from its stored coordinates.
/// Same OSM HOT tiles as the main map (ADR-006) with visible attribution.
class PlaceMiniMap extends StatelessWidget {
  final PlaceModel place;
  final double height;

  const PlaceMiniMap({super.key, required this.place, this.height = 180});

  @override
  Widget build(BuildContext context) {
    final point = LatLng(place.latitude!, place.longitude!);
    final color = AppColors.forCategory(place.categoryName);

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
              urlTemplate:
                  'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
              fallbackUrl:
                  'https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png',
              subdomains: const ['a', 'b', 'c'],
              userAgentPackageName: 'com.wanderai.mobile',
              maxZoom: 19,
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
