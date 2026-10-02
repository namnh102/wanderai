import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import '../data/place_model.dart';
import '../providers/map_provider.dart';
import 'widgets/place_preview_sheet.dart';
import 'widgets/map_category_bar.dart';
import 'widgets/map_search_bar.dart';
import 'widgets/map_radius_selector.dart';

class MapScreen extends ConsumerStatefulWidget {
  const MapScreen({super.key});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen> {
  final MapController _mapController = MapController();
  bool _locationRequested = false;

  @override
  void initState() {
    super.initState();
    // Load initial data after first frame.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initMap();
    });
  }

  Future<void> _initMap() async {
    // Try to get user location; fall back to default (Hanoi).
    await _tryGetLocation();

    final state = ref.read(mapProvider);
    if (state.status == MapLoadingStatus.initial) {
      ref.read(mapProvider.notifier).loadNearby();
    }
  }

  Future<void> _tryGetLocation() async {
    if (_locationRequested) return;
    _locationRequested = true;

    try {
      final permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        final requested = await Geolocator.requestPermission();
        if (requested == LocationPermission.denied ||
            requested == LocationPermission.deniedForever) {
          // Use default location — no error shown.
          return;
        }
      }
      if (permission == LocationPermission.deniedForever) return;

      final serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) return;

      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.medium,
          timeLimit: Duration(seconds: 5),
        ),
      );

      final userLoc = LatLng(position.latitude, position.longitude);
      ref.read(mapProvider.notifier).setUserLocation(userLoc);
      _mapController.move(userLoc, 14.0);
    } catch (_) {
      // Location unavailable — silently use default.
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(mapProvider);
    final theme = Theme.of(context);

    return Scaffold(
      body: Stack(
        children: [
          // ─── Map ───
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: state.center,
              initialZoom: 13.0,
              minZoom: 5.0,
              maxZoom: 18.0,
              onTap: (_, __) => ref.read(mapProvider.notifier).deselectPlace(),
            ),
            children: [
              // OSM Tile Layer
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.wanderai.mobile',
                maxZoom: 18,
              ),

              // Place Markers
              MarkerLayer(
                markers: state.places
                    .where((p) => p.hasCoordinates)
                    .map((place) => _buildMarker(place, state, theme))
                    .toList(),
              ),

              // User location marker
              if (state.useLocation)
                MarkerLayer(
                  markers: [
                    Marker(
                      point: state.center,
                      width: 24,
                      height: 24,
                      child: Container(
                        decoration: BoxDecoration(
                          color: theme.colorScheme.primary,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 3),
                          boxShadow: [
                            BoxShadow(
                              color: theme.colorScheme.primary.withValues(alpha: 0.4),
                              blurRadius: 8,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),

              // Attribution
              const RichAttributionWidget(
                alignment: AttributionAlignment.bottomLeft,
                attributions: [
                  TextSourceAttribution('OpenStreetMap contributors'),
                ],
              ),
            ],
          ),

          // ─── Search Bar (top) ───
          Positioned(
            top: MediaQuery.of(context).padding.top + 8,
            left: 12,
            right: 12,
            child: MapSearchBar(
              onSearch: (query) {
                ref.read(mapProvider.notifier).searchPlaces(query);
              },
              onClear: () {
                ref.read(mapProvider.notifier).searchPlaces('');
              },
            ),
          ),

          // ─── Category filter (below search) ───
          Positioned(
            top: MediaQuery.of(context).padding.top + 68,
            left: 0,
            right: 0,
            child: MapCategoryBar(
              selectedCategory: state.selectedCategory,
              onCategorySelected: (cat) {
                ref.read(mapProvider.notifier).setCategory(cat);
              },
            ),
          ),

          // ─── Radius selector (right side) ───
          Positioned(
            right: 12,
            bottom: (state.selectedPlace != null ? 280 : 24) +
                MediaQuery.of(context).padding.bottom,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // My location button
                _FloatingButton(
                  icon: Icons.my_location,
                  onTap: () => _tryGetLocation(),
                  tooltip: 'Vị trí của tôi',
                ),
                const SizedBox(height: 8),
                MapRadiusSelector(
                  currentRadius: state.radiusKm,
                  onRadiusChanged: (r) {
                    ref.read(mapProvider.notifier).setRadius(r);
                  },
                ),
              ],
            ),
          ),

          // ─── Loading indicator ───
          if (state.status == MapLoadingStatus.loading)
            Positioned(
              top: MediaQuery.of(context).padding.top + 120,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.surface,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.1),
                        blurRadius: 8,
                      ),
                    ],
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: theme.colorScheme.primary,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text('Đang tải...', style: theme.textTheme.bodySmall),
                    ],
                  ),
                ),
              ),
            ),

          // ─── Empty state ───
          if (state.status == MapLoadingStatus.empty)
            Positioned(
              top: MediaQuery.of(context).padding.top + 120,
              left: 40,
              right: 40,
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: theme.colorScheme.surface,
                  borderRadius: BorderRadius.circular(12),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.1),
                      blurRadius: 8,
                    ),
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.location_off, size: 32, color: Colors.grey),
                    const SizedBox(height: 8),
                    Text(
                      'Không tìm thấy địa điểm',
                      style: theme.textTheme.bodyMedium,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Thử mở rộng bán kính hoặc thay đổi bộ lọc',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),

          // ─── Error state ───
          if (state.status == MapLoadingStatus.error)
            Positioned(
              top: MediaQuery.of(context).padding.top + 120,
              left: 40,
              right: 40,
              child: Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: theme.colorScheme.errorContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.error_outline, color: theme.colorScheme.error),
                    const SizedBox(height: 8),
                    Text(
                      state.errorMessage ?? 'Đã xảy ra lỗi',
                      style: theme.textTheme.bodySmall,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 8),
                    TextButton(
                      onPressed: () => ref.read(mapProvider.notifier).loadNearby(),
                      child: const Text('Thử lại'),
                    ),
                  ],
                ),
              ),
            ),

          // ─── Place count badge ───
          if (state.status == MapLoadingStatus.loaded)
            Positioned(
              left: 12,
              bottom: (state.selectedPlace != null ? 280 : 24) +
                  MediaQuery.of(context).padding.bottom,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: theme.colorScheme.primary,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Text(
                  '${state.places.length} địa điểm',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onPrimary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),

          // ─── Place preview sheet (bottom) ───
          if (state.selectedPlace != null)
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: PlacePreviewSheet(
                place: state.selectedPlace!,
                onClose: () => ref.read(mapProvider.notifier).deselectPlace(),
              ),
            ),
        ],
      ),
    );
  }

  Marker _buildMarker(PlaceModel place, MapState state, ThemeData theme) {
    final isSelected = state.selectedPlace?.id == place.id;
    final color = _categoryColor(place.categoryName);

    return Marker(
      point: LatLng(place.latitude!, place.longitude!),
      width: isSelected ? 48 : 36,
      height: isSelected ? 48 : 36,
      child: GestureDetector(
        onTap: () {
          ref.read(mapProvider.notifier).selectPlace(place);
          _mapController.move(
            LatLng(place.latitude!, place.longitude!),
            _mapController.camera.zoom,
          );
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          decoration: BoxDecoration(
            color: isSelected ? color : color.withValues(alpha: 0.9),
            shape: BoxShape.circle,
            border: Border.all(
              color: isSelected ? Colors.white : Colors.white70,
              width: isSelected ? 3 : 2,
            ),
            boxShadow: isSelected
                ? [BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 8)]
                : [BoxShadow(color: Colors.black.withValues(alpha: 0.2), blurRadius: 4)],
          ),
          child: Icon(
            _categoryIcon(place.categoryName),
            color: Colors.white,
            size: isSelected ? 22 : 16,
          ),
        ),
      ),
    );
  }

  Color _categoryColor(String? category) {
    switch (category?.toLowerCase()) {
      case 'attraction':
        return const Color(0xFF9C27B0);
      case 'restaurant':
        return const Color(0xFFFF5722);
      case 'hotel':
        return const Color(0xFF2196F3);
      case 'temple':
      case 'pagoda':
        return const Color(0xFFFF9800);
      case 'beach':
        return const Color(0xFF00BCD4);
      case 'museum':
        return const Color(0xFF607D8B);
      case 'park':
        return const Color(0xFF8BC34A);
      case 'market':
        return const Color(0xFF4CAF50);
      case 'cafe':
        return const Color(0xFF795548);
      default:
        return const Color(0xFF00685F);
    }
  }

  IconData _categoryIcon(String? category) {
    switch (category?.toLowerCase()) {
      case 'attraction':
        return Icons.attractions;
      case 'restaurant':
        return Icons.restaurant;
      case 'hotel':
        return Icons.hotel;
      case 'temple':
      case 'pagoda':
        return Icons.temple_buddhist;
      case 'beach':
        return Icons.beach_access;
      case 'museum':
        return Icons.museum;
      case 'park':
        return Icons.park;
      case 'market':
        return Icons.store;
      case 'cafe':
        return Icons.local_cafe;
      default:
        return Icons.place;
    }
  }
}

class _FloatingButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;
  final String tooltip;

  const _FloatingButton({
    required this.icon,
    required this.onTap,
    required this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Material(
      elevation: 4,
      shape: const CircleBorder(),
      color: theme.colorScheme.surface,
      child: InkWell(
        onTap: onTap,
        customBorder: const CircleBorder(),
        child: Tooltip(
          message: tooltip,
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: Icon(icon, size: 22, color: theme.colorScheme.primary),
          ),
        ),
      ),
    );
  }
}
