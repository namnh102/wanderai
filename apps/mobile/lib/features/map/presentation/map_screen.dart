import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../../location/domain/geo_distance.dart';
import '../../location/providers/user_location_provider.dart';
import '../data/place_model.dart';
import '../providers/map_provider.dart';
import 'widgets/place_preview_sheet.dart';
import 'widgets/map_category_bar.dart';
import 'widgets/map_search_bar.dart';
import 'widgets/map_radius_selector.dart';

class MapScreen extends ConsumerStatefulWidget {
  /// Optional controller, injected only by tests to observe the camera.
  /// In the app it is null and the screen owns its own controller.
  final MapController? mapController;

  const MapScreen({super.key, this.mapController});

  @override
  ConsumerState<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends ConsumerState<MapScreen>
    with TickerProviderStateMixin {
  late final MapController _mapController =
      widget.mapController ?? MapController();
  AnimationController? _cameraAnimationController;
  Timer? _pillDismissTimer;
  bool _showLocationPill = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initMap();
    });
  }

  @override
  void dispose() {
    _pillDismissTimer?.cancel();
    _cameraAnimationController?.dispose();
    super.dispose();
  }

  Future<void> _initMap() async {
    // Load POIs first (around the default map centre); never blocks on GPS.
    ref.read(mapProvider.notifier).loadNearby();
    // Silent: only picks up a fix if permission was already granted. It never
    // prompts and never moves the camera.
    await ref.read(userLocationProvider.notifier).refreshIfPermitted();
  }

  /// Smoothly animates the map camera from current center to [destLocation].
  void _animatedMapMove(LatLng destLocation, double destZoom) {
    _cameraAnimationController?.dispose();

    final latTween = Tween<double>(
      begin: _mapController.camera.center.latitude,
      end: destLocation.latitude,
    );
    final lngTween = Tween<double>(
      begin: _mapController.camera.center.longitude,
      end: destLocation.longitude,
    );
    final zoomTween = Tween<double>(
      begin: _mapController.camera.zoom,
      end: destZoom,
    );

    final controller = AnimationController(
      duration: const Duration(milliseconds: 250),
      vsync: this,
    );
    _cameraAnimationController = controller;

    final animation = CurvedAnimation(
      parent: controller,
      curve: Curves.easeInOutCubic,
    );

    controller.addListener(() {
      _mapController.move(
        LatLng(latTween.evaluate(animation), lngTween.evaluate(animation)),
        zoomTween.evaluate(animation),
      );
    });

    animation.addStatusListener((status) {
      if (status == AnimationStatus.completed ||
          status == AnimationStatus.dismissed) {
        controller.dispose();
        if (_cameraAnimationController == controller) {
          _cameraAnimationController = null;
        }
      }
    });

    controller.forward();
  }

  /// "Vị trí của tôi": explicit request. First tap asks for permission and a
  /// fix; later taps refresh the fix and recenter. The camera is only moved
  /// here, never on passive location updates.
  Future<void> _onMyLocationTap() async {
    setState(() => _showLocationPill = true);
    final pos = await ref.read(userLocationProvider.notifier).request();
    if (!mounted) return;
    if (pos == null) {
      final userLoc = ref.read(userLocationProvider);
      final label = userLoc.label ?? 'Không xác định được vị trí';
      if (userLoc.status == UserLocationStatus.denied) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            SnackBar(
              content: Text(label),
              action: SnackBarAction(
                label: 'Mở cài đặt',
                onPressed: () {
                  ref.read(userLocationProvider.notifier).openAppSettings();
                },
              ),
              duration: const Duration(seconds: 6),
            ),
          );
      } else if (userLoc.status == UserLocationStatus.unavailable) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(
            SnackBar(
              content: Text(label),
              action: SnackBarAction(
                label: 'Mở cài đặt',
                onPressed: () {
                  ref.read(userLocationProvider.notifier).openLocationSettings();
                },
              ),
              duration: const Duration(seconds: 6),
            ),
          );
      }
      return;
    }

    // Zoom policy: if zoomed out (< 14.0), zoom in to 15.0; if already >= 14.0, keep current zoom
    final currentZoom = _mapController.camera.zoom;
    final targetZoom = currentZoom < 14.0 ? 15.0 : currentZoom;

    if (widget.mapController != null) {
      _mapController.move(pos, targetZoom);
    } else {
      _animatedMapMove(pos, targetZoom);
    }

    // Auto-dismiss pill after 5s on successful fix
    _pillDismissTimer?.cancel();
    _pillDismissTimer = Timer(const Duration(seconds: 5), () {
      if (mounted) setState(() => _showLocationPill = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(mapProvider);
    final userLoc = ref.watch(userLocationProvider);
    final userPos = userLoc.position;
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
              maxZoom: 19.0,
              onTap: (_, __) => ref.read(mapProvider.notifier).deselectPlace(),
            ),
            children: [
              // OpenStreetMap Humanitarian (HOT) Basemap Tiles (Reachable in Vietnam, OSM-based, no watermark)
              TileLayer(
                urlTemplate:
                    'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png',
                fallbackUrl:
                    'https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png',
                subdomains: const ['a', 'b', 'c'],
                userAgentPackageName: 'com.wanderai.mobile',
                maxZoom: 19,
              ),

              // Accuracy circle: translucent disk with radius = accuracyMeters
              if (userPos != null &&
                  userLoc.accuracyMeters != null &&
                  userLoc.accuracyMeters! > 0)
                CircleLayer(
                  key: const Key('user_location_accuracy_circle'),
                  circles: [
                    CircleMarker(
                      point: userPos,
                      radius: userLoc.accuracyMeters!,
                      useRadiusInMeter: true,
                      color: AppColors.info.withValues(alpha: 0.12),
                      borderColor: AppColors.info.withValues(alpha: 0.35),
                      borderStrokeWidth: 1.5,
                    ),
                  ],
                ),

              // Current-position marker: real GPS fix only, drawn BEFORE the POI
              // layer so it never covers or intercepts POI taps.
              if (userPos != null)
                MarkerLayer(
                  markers: [
                    Marker(
                      key: const Key('user_location_marker'),
                      point: userPos,
                      width: 44,
                      height: 44,
                      child: IgnorePointer(
                        child: Container(
                          decoration: BoxDecoration(
                            color: AppColors.info.withValues(alpha: 0.18),
                            shape: BoxShape.circle,
                          ),
                          alignment: Alignment.center,
                          child: Container(
                            width: 18,
                            height: 18,
                            decoration: BoxDecoration(
                              color: AppColors.info,
                              shape: BoxShape.circle,
                              border: Border.all(color: Colors.white, width: 3),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withValues(alpha: 0.25),
                                  blurRadius: 4,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),

              // Place Markers
              MarkerLayer(
                markers: state.places
                    .where((p) => p.hasCoordinates)
                    .map((place) => _buildMarker(place, state, theme))
                    .toList(),
              ),

              // Attribution
              const RichAttributionWidget(
                alignment: AttributionAlignment.bottomLeft,
                attributions: [
                  TextSourceAttribution('OpenStreetMap contributors'),
                  TextSourceAttribution('Tiles: Humanitarian OpenStreetMap Team / OSM France'),
                ],
              ),
            ],
          ),

          // ─── Search Bar (top) ───
          Positioned(
            top: MediaQuery.of(context).padding.top + 8,
            left: 0,
            right: 0,
            child: ResponsiveWrapper(
              maxWidth: 600.0,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: MapSearchBar(
                onSearch: (query) {
                  ref.read(mapProvider.notifier).searchPlaces(query);
                },
                onClear: () {
                  ref.read(mapProvider.notifier).searchPlaces('');
                },
              ),
            ),
          ),

          // ─── Category filter (below search) ───
          Positioned(
            top: MediaQuery.of(context).padding.top + 68,
            left: 0,
            right: 0,
            child: ResponsiveWrapper(
              maxWidth: 640.0,
              child: MapCategoryBar(
                selectedCategory: state.selectedCategory,
                onCategorySelected: (cat) {
                  ref.read(mapProvider.notifier).setCategory(cat);
                },
              ),
            ),
          ),

          // ─── Radius selector & Location action (right side) ───
          Positioned(
            right: 12,
            bottom: (state.selectedPlace != null ? 340 : 24) +
                MediaQuery.of(context).padding.bottom,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _LocationButton(
                  key: const Key('my_location_button'),
                  state: userLoc,
                  onTap: _onMyLocationTap,
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
                    color: AppColors.surface,
                    borderRadius: AppRadius.pillRadius,
                    border: Border.all(color: AppColors.border),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.08),
                        blurRadius: 8,
                      ),
                    ],
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(AppColors.primary),
                        ),
                      ),
                      SizedBox(width: 8),
                      Text('Đang tải địa điểm...', style: AppTypography.bodyS),
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
              child: Center(
                child: Container(
                  constraints: const BoxConstraints(maxWidth: 400),
                  padding: const EdgeInsets.all(AppSpacing.md),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: AppRadius.cardRadius,
                    border: Border.all(color: AppColors.border),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.1),
                        blurRadius: 8,
                      ),
                    ],
                  ),
                  child: const Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.location_off_outlined,
                          size: 32, color: AppColors.textTertiary),
                      SizedBox(height: AppSpacing.sm),
                      Text(
                        'Không tìm thấy địa điểm',
                        style: AppTypography.h3,
                        textAlign: TextAlign.center,
                      ),
                      SizedBox(height: 4),
                      Text(
                        'Thử mở rộng bán kính hoặc chọn danh mục khác',
                        style: AppTypography.bodyS,
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
            ),

          // ─── Error state ───
          if (state.status == MapLoadingStatus.error)
            Positioned(
              top: MediaQuery.of(context).padding.top + 120,
              left: 40,
              right: 40,
              child: Center(
                child: Container(
                  constraints: const BoxConstraints(maxWidth: 400),
                  padding: const EdgeInsets.all(AppSpacing.md),
                  decoration: BoxDecoration(
                    color: AppColors.errorContainer,
                    borderRadius: AppRadius.cardRadius,
                    border: Border.all(color: AppColors.error.withValues(alpha: 0.3)),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.error_outline, color: AppColors.error),
                      const SizedBox(height: AppSpacing.sm),
                      Text(
                        state.errorMessage ?? 'Đã xảy ra lỗi',
                        style: AppTypography.bodyS.copyWith(color: AppColors.error),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      TextButton(
                        onPressed: () =>
                            ref.read(mapProvider.notifier).loadNearby(),
                        child: const Text('Thử lại'),
                      ),
                    ],
                  ),
                ),
              ),
            ),

          // ─── Place count badge ───
          if (state.status == MapLoadingStatus.loaded)
            Positioned(
              left: 12,
              bottom: (state.selectedPlace != null ? 340 : 24) +
                  MediaQuery.of(context).padding.bottom,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: AppColors.primaryContainer,
                  borderRadius: AppRadius.pillRadius,
                  border: Border.all(color: AppColors.primary.withValues(alpha: 0.3)),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.08),
                      blurRadius: 4,
                    ),
                  ],
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.place, size: 14, color: AppColors.onPrimaryContainer),
                    const SizedBox(width: 4),
                    Text(
                      '${state.places.length} địa điểm',
                      style: AppTypography.label.copyWith(
                        color: AppColors.onPrimaryContainer,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ),

          // ─── Location status pill (honest state) ───
          if (userLoc.label != null && _showLocationPill)
            Positioned(
              right: 60,
              bottom: (state.selectedPlace != null ? 340 : 24) +
                  MediaQuery.of(context).padding.bottom +
                  8,
              child: GestureDetector(
                onTap: () {
                  _pillDismissTimer?.cancel();
                  setState(() => _showLocationPill = false);
                },
                child: Container(
                  key: const Key('location_status_pill'),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: AppRadius.pillRadius,
                    border: Border.all(
                      color: userLoc.status == UserLocationStatus.denied ||
                              userLoc.status == UserLocationStatus.unavailable
                          ? AppColors.error.withValues(alpha: 0.3)
                          : (userLoc.quality == LocationAccuracyQuality.approximate ||
                                  userLoc.quality == LocationAccuracyQuality.poor)
                              ? AppColors.warning.withValues(alpha: 0.5)
                              : AppColors.border,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.08),
                        blurRadius: 4,
                      ),
                    ],
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        userLoc.status == UserLocationStatus.denied
                            ? Icons.location_disabled
                            : userLoc.status == UserLocationStatus.unavailable
                                ? Icons.location_off
                                : userLoc.quality == LocationAccuracyQuality.good
                                    ? Icons.check_circle_outline
                                    : userLoc.quality == LocationAccuracyQuality.approximate
                                        ? Icons.info_outline
                                        : Icons.warning_amber_rounded,
                        size: 14,
                        color: userLoc.status == UserLocationStatus.denied ||
                                userLoc.status == UserLocationStatus.unavailable
                            ? AppColors.error
                            : userLoc.quality == LocationAccuracyQuality.good
                                ? AppColors.info
                                : AppColors.warning,
                      ),
                      const SizedBox(width: 6),
                      Text(
                        userLoc.label!,
                        style: AppTypography.label.copyWith(
                          color: userLoc.status == UserLocationStatus.denied ||
                                  userLoc.status == UserLocationStatus.unavailable
                              ? AppColors.error
                              : userLoc.quality == LocationAccuracyQuality.good
                                  ? AppColors.info
                                  : AppColors.textPrimary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
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
                distanceKm: distanceFromUserKm(
                  userPos,
                  state.selectedPlace!.latitude,
                  state.selectedPlace!.longitude,
                ),
                onClose: () => ref.read(mapProvider.notifier).deselectPlace(),
                // push (not go): MapScreen and its state stay alive beneath the detail.
                onViewDetail: () =>
                    context.push('/places/${state.selectedPlace!.id}'),
              ),
            ),
        ],
      ),
    );
  }

  Marker _buildMarker(PlaceModel place, MapState state, ThemeData theme) {
    final isSelected = state.selectedPlace?.id == place.id;
    final color = AppColors.forCategory(place.categoryName);

    return Marker(
      point: LatLng(place.latitude!, place.longitude!),
      width: isSelected ? 48 : 36,
      height: isSelected ? 48 : 36,
      child: GestureDetector(
        onTap: () {
          ref.read(mapProvider.notifier).selectPlace(place);
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
                : [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.2),
                      blurRadius: 4,
                    )
                  ],
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
      case 'culture':
        return Icons.museum;
      case 'park':
      case 'nature':
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

/// Visual states for the "Vị trí của tôi" floating action:
/// - idle: default state before fix
/// - requesting: loading spinner
/// - success: accurate fix (<= 50m)
/// - approximate: approximate/poor fix (> 50m)
/// - denied: permission denied
/// - unavailable: location service disabled or error
class _LocationButton extends StatelessWidget {
  final UserLocationState state;
  final VoidCallback onTap;

  const _LocationButton({
    super.key,
    required this.state,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    IconData icon;
    Color iconColor;
    String tooltip;
    Widget? customChild;

    switch (state.status) {
      case UserLocationStatus.unknown:
        icon = Icons.my_location;
        iconColor = AppColors.textSecondary;
        tooltip = 'Vị trí của tôi';
        break;
      case UserLocationStatus.requesting:
        icon = Icons.my_location;
        iconColor = AppColors.primary;
        tooltip = 'Đang xác định vị trí...';
        customChild = const SizedBox(
          width: 20,
          height: 20,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            valueColor: AlwaysStoppedAnimation<Color>(AppColors.primary),
          ),
        );
        break;
      case UserLocationStatus.denied:
        icon = Icons.location_disabled;
        iconColor = AppColors.error;
        tooltip = 'Quyền vị trí bị từ chối';
        break;
      case UserLocationStatus.unavailable:
        icon = Icons.location_off;
        iconColor = AppColors.textTertiary;
        tooltip = 'Không xác định được vị trí';
        break;
      case UserLocationStatus.granted:
        if (state.quality == LocationAccuracyQuality.good) {
          icon = Icons.my_location;
          iconColor = AppColors.info;
          tooltip = 'Vị trí chính xác (±${state.accuracyMeters?.round()}m)';
        } else {
          icon = Icons.location_searching;
          iconColor = AppColors.warning;
          tooltip = 'Vị trí ước lượng (±${state.accuracyMeters?.round()}m)';
        }
        break;
    }

    return Material(
      elevation: 3,
      shape: const CircleBorder(),
      color: AppColors.surface,
      child: InkWell(
        onTap: onTap,
        customBorder: const CircleBorder(),
        child: Tooltip(
          message: tooltip,
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: customChild ?? Icon(icon, size: 22, color: iconColor),
          ),
        ),
      ),
    );
  }
}
