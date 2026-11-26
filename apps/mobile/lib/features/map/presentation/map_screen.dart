import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/app_state_banner.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../../location/domain/geo_distance.dart';
import '../../location/providers/user_location_provider.dart';
import '../data/cached_offline_tile_provider.dart';
import '../data/offline_tile_downloader.dart';
import '../data/place_model.dart';
import '../providers/map_provider.dart';
import 'widgets/place_preview_sheet.dart';
import 'widgets/map_category_bar.dart';
import 'widgets/map_search_bar.dart';
import 'widgets/map_destination_selector.dart';
import 'widgets/map_radius_selector.dart';
import 'widgets/offline_map_sheet.dart';

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
  final TextEditingController _searchController = TextEditingController();
  final GlobalKey _previewSheetKey = GlobalKey();
  final StreamController<void> _tileResetController =
      StreamController<void>.broadcast();
  late final CachedOfflineTileProvider _tileProvider;
  bool _isOutsideOfflineBounds = false;
  bool _isOutsideOfflineZoom = false;
  double? _currentCameraZoom;
  bool _hasUncachedTileErrorsInView = false;
  ScaffoldFeatureController<SnackBar, SnackBarClosedReason>?
      _locationSnackBarController;

  @override
  void initState() {
    super.initState();
    _tileProvider = CachedOfflineTileProvider(
      store: ref.read(offlineTileStoreProvider),
      dio: ref.read(offlineTileDioProvider),
      isOfflineOnly: () => mounted && ref.read(mapProvider).isOfflineMode,
      onNetworkTileLoaded: () {
        if (!mounted || !_hasUncachedTileErrorsInView) return;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted && _hasUncachedTileErrorsInView) {
            setState(() => _hasUncachedTileErrorsInView = false);
          }
        });
      },
    );
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initMap();
    });
  }

  @override
  void dispose() {
    _pillDismissTimer?.cancel();
    _cameraAnimationController?.dispose();
    _cameraAnimationController = null;
    _searchController.dispose();
    _tileResetController.close();
    super.dispose();
  }

  void _handleCameraPositionChanged(MapCamera camera) {
    final region = ref.read(mapProvider).cachedHalongRegion;
    final outsideBounds =
        region != null && !region.bbox.contains(camera.center);
    final outsideZoom = region != null && !region.containsZoom(camera.zoom);
    final zoomChangedSignificantly = outsideZoom &&
        (_currentCameraZoom == null ||
            (_currentCameraZoom! - camera.zoom).abs() >= 0.1);
    final backInside = !outsideBounds && !outsideZoom;

    if (outsideBounds != _isOutsideOfflineBounds ||
        outsideZoom != _isOutsideOfflineZoom ||
        zoomChangedSignificantly ||
        (backInside && _hasUncachedTileErrorsInView)) {
      setState(() {
        _isOutsideOfflineBounds = outsideBounds;
        _isOutsideOfflineZoom = outsideZoom;
        _currentCameraZoom = camera.zoom;
        if (backInside) {
          _hasUncachedTileErrorsInView = false;
        }
      });
    }
  }

  Future<void> _initMap() async {
    // Load the default destination (Hà Nội) first; never blocks on GPS.
    ref.read(mapProvider.notifier).ensureInitialized();
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

  /// Applies a [MapCameraRequest] emitted by the notifier. Called only from a
  /// provider listener (never from build). A newer request cancels any
  /// animation still running for an older one.
  void _applyCameraRequest(MapCameraRequest req) {
    if (!mounted) return;
    _cameraAnimationController?.dispose();
    _cameraAnimationController = null;

    if (req.fitPoints.length > 1) {
      final bounds = LatLngBounds.fromPoints(req.fitPoints);
      final identical = bounds.south == bounds.north && bounds.west == bounds.east;
      if (!identical) {
        _mapController.fitCamera(
          CameraFit.bounds(
            bounds: bounds,
            padding: const EdgeInsets.fromLTRB(56, 250, 56, 150),
            maxZoom: 17,
          ),
        );
        return;
      }
      _mapController.move(req.fitPoints.first, singleResultZoom);
      return;
    }

    if (widget.mapController != null) {
      _mapController.move(req.center, req.zoom);
    } else {
      _animatedMapMove(req.center, req.zoom);
    }
  }

  /// Displays a floating GPS recovery SnackBar positioned safely above
  /// [PlacePreviewSheet] and bottom map controls whenever a marker is selected,
  /// preventing occlusion of the `Xem chi tiết` CTA.
  void _showLocationErrorSnackBar(UserLocationState userLoc) {
    if (!mounted) return;
    final isDenied = userLoc.status == UserLocationStatus.denied;
    final isUnavailable = userLoc.status == UserLocationStatus.unavailable;
    if (!isDenied && !isUnavailable) return;

    final String message;
    if (isDenied &&
        userLoc.permissionState == LocationPermissionState.deniedForever) {
      message =
          'Quyền vị trí đã bị từ chối vĩnh viễn. Vui lòng bật trong Cài đặt.';
    } else {
      message = userLoc.label ?? 'Không xác định được vị trí';
    }

    final hasSelectedPlace = ref.read(mapProvider).selectedPlace != null;
    final mq = MediaQuery.of(context);
    final textScale = mq.textScaler.scale(14.0) / 14.0;
    double bottomMargin = 80.0 + mq.padding.bottom;
    if (hasSelectedPlace) {
      final sheetBox =
          _previewSheetKey.currentContext?.findRenderObject() as RenderBox?;
      final sheetHeight =
          sheetBox?.hasSize == true ? sheetBox!.size.height : 280.0;
      final minAboveSheet = sheetHeight + 12.0;
      final desiredAboveControls =
          math.max(sheetHeight + 64.0, 396.0 + mq.padding.bottom);
      final reservedForSnackBar = textScale > 1.2 ? 270.0 : 220.0;
      final maxAllowed = math.max(
        minAboveSheet,
        mq.size.height - mq.padding.top - reservedForSnackBar,
      );
      bottomMargin = desiredAboveControls.clamp(minAboveSheet, maxAllowed);
    }

    final messenger = ScaffoldMessenger.of(context);
    messenger.removeCurrentSnackBar();
    late final ScaffoldFeatureController<SnackBar, SnackBarClosedReason>
        controller;
    controller = messenger.showSnackBar(
      SnackBar(
        key: const Key('map_location_error_snackbar'),
        behavior: SnackBarBehavior.floating,
        margin: EdgeInsets.fromLTRB(8, 0, 8, bottomMargin),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        content: Text(
          message,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        action: SnackBarAction(
          label: 'Mở cài đặt',
          onPressed: () {
            if (isDenied) {
              ref.read(userLocationProvider.notifier).openAppSettings();
            } else {
              ref.read(userLocationProvider.notifier).openLocationSettings();
            }
          },
        ),
        duration: const Duration(seconds: 6),
      ),
    );
    _locationSnackBarController = controller;
    controller.closed.then((_) {
      if (_locationSnackBarController == controller) {
        _locationSnackBarController = null;
      }
    });
  }

  /// "Vị trí của tôi": explicit request. First tap asks for permission and a
  /// fix; later taps refresh the fix and recenter. The camera is only moved
  /// here, never on passive location updates.
  Future<void> _onMyLocationTap() async {
    setState(() => _showLocationPill = true);
    final pos = await ref.read(userLocationProvider.notifier).request();
    if (!mounted) return;
    if (pos == null) {
      _showLocationErrorSnackBar(ref.read(userLocationProvider));
      return;
    }

    if (_locationSnackBarController != null) {
      ScaffoldMessenger.of(context).removeCurrentSnackBar();
      _locationSnackBarController = null;
    }

    // Zoom policy: if zoomed out (< 14.0), zoom in to 15.0; if already >= 14.0, keep current zoom
    final currentZoom = _mapController.camera.zoom;
    final targetZoom = currentZoom < 14.0 ? 15.0 : currentZoom;

    // Enter NEARBY mode: clears search/destination highlight, loads nearby.
    _searchController.clear();
    ref.read(mapProvider.notifier).setUserLocation(pos);

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
    final mediaQuery = MediaQuery.of(context);
    final topInset = mediaQuery.padding.top;
    final textScale = mediaQuery.textScaler.scale(14.0) / 14.0;
    final isCompactOverlay = mediaQuery.size.width < 420 || textScale > 1.25;

    // Camera moves are driven by events, never from build().
    ref.listen<MapCameraRequest?>(
      mapProvider.select((s) => s.cameraRequest),
      (prev, next) {
        if (next != null && next.seq != prev?.seq) _applyCameraRequest(next);
      },
    );
    // Reset cached tiles when download completes or cache is cleared.
    ref.listen<int>(
      mapProvider.select((s) => s.tileLayerResetEpoch),
      (prev, next) {
        if (prev != next && mounted) {
          _tileProvider.cacheEpoch = next;
          _hasUncachedTileErrorsInView = false;
          _tileResetController.add(null);
        }
      },
    );
    // Sync boundary flags when cachedHalongRegion is populated or cleared.
    ref.listen(
      mapProvider.select((s) => s.cachedHalongRegion),
      (prev, next) {
        if (!mounted) return;
        if ((prev == null) != (next == null)) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) return;
            try {
              _handleCameraPositionChanged(_mapController.camera);
            } catch (_) {}
          });
        }
      },
    );
    // Search text is cleared when the search is left by other means.
    ref.listen<String?>(mapProvider.select((s) => s.searchQuery), (prev, next) {
      if (next == null && _searchController.text.isNotEmpty) {
        _searchController.clear();
      }
    });
    // Reposition active GPS error SnackBar whenever PlacePreviewSheet opens/closes
    // so `Xem chi tiết` is never occluded.
    ref.listen<PlaceModel?>(
      mapProvider.select((s) => s.selectedPlace),
      (prev, next) {
        if ((prev == null) != (next == null) &&
            _locationSnackBarController != null) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (mounted && _locationSnackBarController != null) {
              _showLocationErrorSnackBar(ref.read(userLocationProvider));
            }
          });
        }
      },
    );

    final hasOfflineBoundaryContext =
        state.isOfflineMode || _hasUncachedTileErrorsInView;
    final suppressOfflineBadgeForSelectedOverlay =
        state.selectedPlace != null &&
            (state.status == MapLoadingStatus.loading ||
                state.status == MapLoadingStatus.empty ||
                state.status == MapLoadingStatus.error);
    final showOfflineBadge = state.isOfflineMode &&
        state.cachedHalongRegion != null &&
        !_isOutsideOfflineBounds &&
        !_isOutsideOfflineZoom &&
        !suppressOfflineBadgeForSelectedOverlay;
    final showOfflineBoundaryBanner = state.cachedHalongRegion != null &&
        hasOfflineBoundaryContext &&
        (_isOutsideOfflineBounds || _isOutsideOfflineZoom);
    final suppressBadgesForBanner =
        showOfflineBoundaryBanner && state.selectedPlace != null;
    final showCountBadge =
        state.status == MapLoadingStatus.loaded && !suppressBadgesForBanner;
    final suppressPillForOverlay = state.selectedPlace != null &&
        (showOfflineBoundaryBanner ||
            state.status == MapLoadingStatus.loading ||
            state.status == MapLoadingStatus.empty ||
            state.status == MapLoadingStatus.error);
    final showPill =
        userLoc.label != null && _showLocationPill && !suppressPillForOverlay;

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
              onPositionChanged: (camera, _) =>
                  _handleCameraPositionChanged(camera),
            ),
            children: [
              // OpenStreetMap Humanitarian (HOT) Basemap Tiles (Reachable in Vietnam, OSM-based, no watermark)
              TileLayer(
                urlTemplate: OfflineTileDownloader.primaryUrlTemplate,
                fallbackUrl: OfflineTileDownloader.fallbackUrlTemplate,
                subdomains: OfflineTileDownloader.subdomains,
                userAgentPackageName: 'com.wanderai.mobile',
                maxZoom: 19,
                tileProvider: _tileProvider,
                reset: _tileResetController.stream,
                evictErrorTileStrategy:
                    EvictErrorTileStrategy.notVisibleRespectMargin,
                errorImage: MemoryImage(TileProvider.transparentImage),
                errorTileCallback: (tile, error, stackTrace) {
                  if (!mounted) return;
                  final currentState = ref.read(mapProvider);
                  if (currentState.cachedHalongRegion == null &&
                      !currentState.isOfflineMode) {
                    return;
                  }
                  if (!_hasUncachedTileErrorsInView) {
                    WidgetsBinding.instance.addPostFrameCallback((_) {
                      if (!mounted || _hasUncachedTileErrorsInView) return;
                      final region = ref.read(mapProvider).cachedHalongRegion;
                      var outsideBounds = _isOutsideOfflineBounds;
                      var outsideZoom = _isOutsideOfflineZoom;
                      var cameraZoom = _currentCameraZoom;
                      if (region != null) {
                        try {
                          final camera = _mapController.camera;
                          outsideBounds = !region.bbox.contains(camera.center);
                          outsideZoom = !region.containsZoom(camera.zoom);
                          cameraZoom = camera.zoom;
                        } catch (_) {}
                      }
                      setState(() {
                        _hasUncachedTileErrorsInView = true;
                        _isOutsideOfflineBounds = outsideBounds;
                        _isOutsideOfflineZoom = outsideZoom;
                        _currentCameraZoom = cameraZoom;
                      });
                    });
                  }
                },
                tileBuilder: (context, tileWidget, tile) {
                  if (tile.loadError &&
                      (state.isOfflineMode ||
                          state.cachedHalongRegion != null)) {
                    return Container(
                      decoration: BoxDecoration(
                        color: AppColors.surfaceContainer
                            .withValues(alpha: 0.85),
                        border: Border.all(
                          color: AppColors.softBorder,
                          width: 0.5,
                        ),
                      ),
                      alignment: Alignment.center,
                      padding: const EdgeInsets.all(4),
                      child: Text(
                        'Chưa tải\nngoại tuyến\nz${tile.coordinates.z}',
                        textAlign: TextAlign.center,
                        style: AppTypography.label.copyWith(
                          fontSize: 10,
                          color: AppColors.textTertiary,
                        ),
                      ),
                    );
                  }
                  return tileWidget;
                },
              ),

              // Downloaded offline region boundary polygon
              if (state.cachedHalongRegion != null)
                PolygonLayer(
                  polygons: [
                    Polygon(
                      points: state.cachedHalongRegion!.bbox.polygonPoints,
                      color: AppColors.primary.withValues(alpha: 0.06),
                      borderColor: AppColors.primary,
                      borderStrokeWidth: 2.0,
                      pattern: StrokePattern.dashed(segments: const [10, 6]),
                      label: 'Vùng ngoại tuyến Hạ Long',
                      labelStyle: AppTypography.label.copyWith(
                        color: AppColors.primaryDeep,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
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
                controller: _searchController,
                onSearch: (query) {
                  ref.read(mapProvider.notifier).searchPlaces(query);
                },
                onClear: () {
                  ref.read(mapProvider.notifier).searchPlaces('');
                },
              ),
            ),
          ),

          // ─── Destination selector (below search) ───
          Positioned(
            top: topInset + 64,
            left: 0,
            right: 0,
            child: ResponsiveWrapper(
              maxWidth: 640.0,
              child: MapDestinationSelector(
                selectedSlug: state.mode == MapMode.destination
                    ? state.activeDestinationSlug
                    : null,
                onSelected: (slug) {
                  _searchController.clear();
                  ref.read(mapProvider.notifier).selectDestination(slug);
                },
              ),
            ),
          ),

          // ─── Category filter (below destination chips) ───
          Positioned(
            top: topInset + 112,
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

          // ─── Offline badge / boundary banner & map loading/empty/error states ───
          if (showOfflineBadge ||
              showOfflineBoundaryBanner ||
              (!suppressBadgesForBanner &&
                  (state.status == MapLoadingStatus.loading ||
                      state.status == MapLoadingStatus.empty ||
                      state.status == MapLoadingStatus.error)))
            Positioned(
              top: topInset + 162,
              left: 0,
              right: 0,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (showOfflineBadge)
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Padding(
                        padding: EdgeInsets.only(
                          left: 12,
                          right: (state.mode == MapMode.nearby &&
                                  state.selectedPlace != null)
                              ? 132
                              : (state.selectedPlace != null ? 64 : 12),
                        ),
                        child: GestureDetector(
                          onTap: () => showOfflineMapSheet(context),
                          child: Container(
                            key: const Key('offline_mode_badge'),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 6,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.primaryContainer,
                              borderRadius: AppRadius.pillRadius,
                              border: Border.all(
                                color: AppColors.primary
                                    .withValues(alpha: 0.35),
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
                                const Icon(
                                  Icons.offline_pin,
                                  size: 15,
                                  color: AppColors.primaryDeep,
                                ),
                                const SizedBox(width: 6),
                                Flexible(
                                  child: Text(
                                    'Chế độ ngoại tuyến · Hạ Long '
                                    '(z${state.cachedHalongRegion!.minZoom}–z${state.cachedHalongRegion!.maxZoom})',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: AppTypography.label.copyWith(
                                      color: AppColors.primaryDeep,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ),
                  if (showOfflineBoundaryBanner)
                    Padding(
                      padding: EdgeInsets.only(
                        left: 12,
                        right: (state.mode == MapMode.nearby &&
                                state.selectedPlace != null)
                            ? 132
                            : (state.selectedPlace != null ? 64 : 12),
                      ),
                      child: ResponsiveWrapper(
                        maxWidth: 600.0,
                        child: Material(
                          color: AppColors.surface,
                          borderRadius: AppRadius.mdRadius,
                          elevation: 2,
                          child: _OfflineBoundaryBanner(
                            key: const Key('offline_boundary_banner'),
                            message: _isOutsideOfflineBounds
                                ? 'Ngoài vùng bản đồ ngoại tuyến đã tải '
                                    '(Hạ Long z${state.cachedHalongRegion!.minZoom}–z${state.cachedHalongRegion!.maxZoom})'
                                : 'Mức zoom hiện tại (${(_currentCameraZoom ?? 15.0).toStringAsFixed(1)}) '
                                    'ngoài phạm vi đã tải '
                                    '(z${state.cachedHalongRegion!.minZoom}–z${state.cachedHalongRegion!.maxZoom})',
                            onRecenter: () => ref
                                .read(mapProvider.notifier)
                                .recenterToOfflineRegion(),
                          ),
                        ),
                      ),
                    ),
                  if ((showOfflineBadge || showOfflineBoundaryBanner) &&
                      !suppressBadgesForBanner &&
                      (state.status == MapLoadingStatus.loading ||
                          state.status == MapLoadingStatus.empty ||
                          state.status == MapLoadingStatus.error))
                    const SizedBox(height: 8),
                  if (state.status == MapLoadingStatus.loading &&
                      !suppressBadgesForBanner)
                    Padding(
                      padding: EdgeInsets.only(
                        left: 12,
                        right: state.mode == MapMode.nearby
                            ? (state.selectedPlace != null ? 132 : 92)
                            : 64,
                      ),
                      child: MediaQuery.withClampedTextScaling(
                        maxScaleFactor: 1.3,
                        child: Center(
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 8,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.surface,
                              borderRadius: AppRadius.pillRadius,
                              border: Border.all(color: AppColors.softBorder),
                              boxShadow: [
                                BoxShadow(
                                  color: AppColors.primaryDeep
                                      .withValues(alpha: 0.08),
                                  blurRadius: 8,
                                ),
                              ],
                            ),
                            child: const AppLoading(
                              isCompact: true,
                              message: 'Đang tải địa điểm...',
                            ),
                          ),
                        ),
                      ),
                    ),
                  if (state.status == MapLoadingStatus.empty &&
                      !suppressBadgesForBanner)
                    if (state.selectedPlace != null)
                      Padding(
                        padding: EdgeInsets.only(
                          left: 12,
                          right: state.mode == MapMode.nearby ? 132 : 64,
                        ),
                        child: MediaQuery.withClampedTextScaling(
                          maxScaleFactor: 1.1,
                          child: Center(
                            child: Container(
                              constraints: const BoxConstraints(maxWidth: 400),
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 5,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.surface,
                                borderRadius: AppRadius.mdRadius,
                                border: Border.all(color: AppColors.softBorder),
                                boxShadow: [
                                  BoxShadow(
                                    color: AppColors.primaryDeep
                                        .withValues(alpha: 0.1),
                                    blurRadius: 8,
                                  ),
                                ],
                              ),
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      const Icon(
                                        Icons.location_off_outlined,
                                        size: 16,
                                        color: AppColors.textTertiary,
                                      ),
                                      const SizedBox(width: 6),
                                      Expanded(
                                        child: Text(
                                          'Không tìm thấy địa điểm',
                                          style: AppTypography.label.copyWith(
                                            fontSize: 11.5,
                                            height: 1.15,
                                            fontWeight: FontWeight.w700,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    _emptyHint(state),
                                    key: const Key('map_empty_hint'),
                                    maxLines: 3,
                                    overflow: TextOverflow.ellipsis,
                                    style: AppTypography.caption.copyWith(
                                      fontSize: 10.5,
                                      height: 1.15,
                                      color: AppColors.textTertiary,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      )
                    else
                      Padding(
                        padding: EdgeInsets.only(
                          left: 12,
                          right: state.mode == MapMode.nearby ? 92 : 64,
                        ),
                        child: MediaQuery.withClampedTextScaling(
                          maxScaleFactor: 1.25,
                          child: Center(
                            child: Container(
                              constraints: const BoxConstraints(maxWidth: 400),
                              padding: EdgeInsets.symmetric(
                                horizontal:
                                    isCompactOverlay ? 12 : AppSpacing.md,
                                vertical: isCompactOverlay ? 10 : AppSpacing.md,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.surface,
                                borderRadius: isCompactOverlay
                                    ? AppRadius.mdRadius
                                    : AppRadius.cardRadius,
                                border: Border.all(color: AppColors.softBorder),
                                boxShadow: [
                                  BoxShadow(
                                    color: AppColors.primaryDeep
                                        .withValues(alpha: 0.1),
                                    blurRadius: 8,
                                  ),
                                ],
                              ),
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    Icons.location_off_outlined,
                                    size: isCompactOverlay ? 22 : 32,
                                    color: AppColors.textTertiary,
                                  ),
                                  SizedBox(
                                    height:
                                        isCompactOverlay ? 4 : AppSpacing.sm,
                                  ),
                                  Text(
                                    'Không tìm thấy địa điểm',
                                    maxLines: isCompactOverlay ? 2 : null,
                                    overflow: isCompactOverlay
                                        ? TextOverflow.ellipsis
                                        : null,
                                    style: isCompactOverlay
                                        ? AppTypography.h3.copyWith(
                                            fontSize: 15,
                                            height: 1.2,
                                          )
                                        : AppTypography.h3,
                                    textAlign: TextAlign.center,
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    _emptyHint(state),
                                    key: const Key('map_empty_hint'),
                                    maxLines: isCompactOverlay ? 3 : null,
                                    overflow: isCompactOverlay
                                        ? TextOverflow.ellipsis
                                        : null,
                                    style: isCompactOverlay
                                        ? AppTypography.bodyS.copyWith(
                                            fontSize: 12,
                                            height: 1.25,
                                          )
                                        : AppTypography.bodyS,
                                    textAlign: TextAlign.center,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ),
                  if (state.status == MapLoadingStatus.error &&
                      !suppressBadgesForBanner)
                    Padding(
                      padding: EdgeInsets.only(
                        left: 12,
                        right: state.mode == MapMode.nearby
                            ? (state.selectedPlace != null ? 132 : 92)
                            : 64,
                      ),
                      child: Center(
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 440),
                          child: MediaQuery.withClampedTextScaling(
                            maxScaleFactor: 1.3,
                            child: Material(
                              color: AppColors.surface,
                              borderRadius: AppRadius.mdRadius,
                              elevation: 2,
                              child: AppStateBanner(
                                message:
                                    state.errorMessage ?? 'Đã xảy ra lỗi',
                                tone: AppStateBannerTone.error,
                                actionLabel: 'Thử lại',
                                maxLines: state.selectedPlace != null
                                    ? 2
                                    : (isCompactOverlay ? 3 : null),
                                compact: state.selectedPlace != null ||
                                    isCompactOverlay,
                                onAction: () =>
                                    ref.read(mapProvider.notifier).retry(),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ),

          // ─── Radius selector & Location action (right side) ───
          Positioned(
            right: 12,
            bottom: (state.selectedPlace != null ? 320 : 24) +
                MediaQuery.of(context).padding.bottom,
            child: state.mode == MapMode.nearby && state.selectedPlace != null
                ? Row(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      MapRadiusSelector(
                        currentRadius: state.radiusKm,
                        onRadiusChanged: (r) {
                          ref.read(mapProvider.notifier).setRadius(r);
                        },
                      ),
                      const SizedBox(width: 8),
                      Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          _OfflineMapButton(
                            key: const Key('offline_map_button'),
                            hasCache: state.cachedHalongRegion != null,
                            isOfflineMode: state.isOfflineMode,
                            isDownloading: state.isDownloadingOffline,
                            onTap: () => showOfflineMapSheet(context),
                          ),
                          const SizedBox(height: 8),
                          _LocationButton(
                            key: const Key('my_location_button'),
                            state: userLoc,
                            onTap: _onMyLocationTap,
                          ),
                        ],
                      ),
                    ],
                  )
                : Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _OfflineMapButton(
                        key: const Key('offline_map_button'),
                        hasCache: state.cachedHalongRegion != null,
                        isOfflineMode: state.isOfflineMode,
                        isDownloading: state.isDownloadingOffline,
                        onTap: () => showOfflineMapSheet(context),
                      ),
                      const SizedBox(height: 8),
                      _LocationButton(
                        key: const Key('my_location_button'),
                        state: userLoc,
                        onTap: _onMyLocationTap,
                      ),
                      if (state.mode == MapMode.nearby) ...[
                        const SizedBox(height: 8),
                        MapRadiusSelector(
                          currentRadius: state.radiusKm,
                          onRadiusChanged: (r) {
                            ref.read(mapProvider.notifier).setRadius(r);
                          },
                        ),
                      ],
                    ],
                  ),
          ),

          // ─── Place count badge & Location status pill ───
          if (showCountBadge || showPill)
            Positioned(
              left: 12,
              right: state.mode == MapMode.nearby
                  ? (state.selectedPlace != null ? 132 : 88)
                  : 64,
              bottom: (state.selectedPlace != null ? 320 : 24) +
                  MediaQuery.of(context).padding.bottom,
              child: Builder(
                builder: (context) {
                  final countBadge = Container(
                    key: const Key('place_count_badge'),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.primaryContainer,
                      borderRadius: AppRadius.pillRadius,
                      border: Border.all(
                        color: AppColors.primary.withValues(alpha: 0.3),
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
                        const Icon(
                          Icons.place,
                          size: 14,
                          color: AppColors.onPrimaryContainer,
                        ),
                        const SizedBox(width: 4),
                        Flexible(
                          child: Text(
                            '${state.places.length} địa điểm',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: AppTypography.label.copyWith(
                              color: AppColors.onPrimaryContainer,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                  );

                  final locationPill = GestureDetector(
                    onTap: () {
                      _pillDismissTimer?.cancel();
                      setState(() => _showLocationPill = false);
                    },
                    child: Container(
                      key: const Key('location_status_pill'),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        borderRadius: AppRadius.pillRadius,
                        border: Border.all(
                          color: userLoc.status == UserLocationStatus.denied ||
                                  userLoc.status ==
                                      UserLocationStatus.unavailable
                              ? AppColors.error.withValues(alpha: 0.3)
                              : (userLoc.quality ==
                                          LocationAccuracyQuality.approximate ||
                                      userLoc.quality ==
                                          LocationAccuracyQuality.poor)
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
                                : userLoc.status ==
                                        UserLocationStatus.unavailable
                                    ? Icons.location_off
                                    : userLoc.quality ==
                                            LocationAccuracyQuality.good
                                        ? Icons.check_circle_outline
                                        : userLoc.quality ==
                                                LocationAccuracyQuality
                                                    .approximate
                                            ? Icons.info_outline
                                            : Icons.warning_amber_rounded,
                            size: 14,
                            color: userLoc.status ==
                                        UserLocationStatus.denied ||
                                    userLoc.status ==
                                        UserLocationStatus.unavailable
                                ? AppColors.error
                                : userLoc.quality ==
                                        LocationAccuracyQuality.good
                                    ? AppColors.info
                                    : AppColors.warning,
                          ),
                          const SizedBox(width: 6),
                          Flexible(
                            child: Text(
                              userLoc.label ?? '',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: AppTypography.label.copyWith(
                                color: userLoc.status ==
                                            UserLocationStatus.denied ||
                                        userLoc.status ==
                                            UserLocationStatus.unavailable
                                    ? AppColors.error
                                    : userLoc.quality ==
                                            LocationAccuracyQuality.good
                                        ? AppColors.info
                                        : AppColors.textPrimary,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  );

                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    mainAxisAlignment: showCountBadge
                        ? MainAxisAlignment.spaceBetween
                        : MainAxisAlignment.end,
                    children: [
                      if (showCountBadge)
                        Flexible(
                          flex: showPill ? 2 : 1,
                          child: countBadge,
                        ),
                      if (showCountBadge && showPill) const SizedBox(width: 8),
                      if (showPill)
                        Flexible(
                          flex: showCountBadge ? 3 : 1,
                          child: Padding(
                            padding: const EdgeInsets.only(bottom: 4),
                            child: locationPill,
                          ),
                        ),
                    ],
                  );
                },
              ),
            ),

          // ─── Place preview sheet (bottom) ───
          if (state.selectedPlace != null)
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: PlacePreviewSheet(
                key: _previewSheetKey,
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

  String _emptyHint(MapState state) {
    switch (state.mode) {
      case MapMode.search:
        return 'Không có địa điểm đã xác minh khớp với "${state.searchQuery ?? ''}". Hãy thử từ khóa khác.';
      case MapMode.destination:
        return 'Chưa có địa điểm trong danh mục này. Hãy chọn danh mục khác.';
      case MapMode.nearby:
        return 'Thử mở rộng bán kính hoặc chọn danh mục khác';
    }
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
          child: Center(child: AppLoading(isCompact: true)),
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

class _OfflineMapButton extends StatelessWidget {
  final bool hasCache;
  final bool isOfflineMode;
  final bool isDownloading;
  final VoidCallback onTap;

  const _OfflineMapButton({
    super.key,
    required this.hasCache,
    required this.isOfflineMode,
    required this.isDownloading,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final iconColor = isOfflineMode
        ? AppColors.warning
        : hasCache
            ? AppColors.primary
            : AppColors.textSecondary;

    return Material(
      elevation: 3,
      shape: const CircleBorder(),
      color: AppColors.surface,
      child: InkWell(
        onTap: onTap,
        customBorder: const CircleBorder(),
        child: Tooltip(
          message: 'Bản đồ ngoại tuyến',
          child: Padding(
            padding: const EdgeInsets.all(10),
            child: isDownloading
                ? const SizedBox(
                    width: 22,
                    height: 22,
                    child: Center(child: AppLoading(isCompact: true)),
                  )
                : Icon(
                    hasCache
                        ? Icons.offline_pin_outlined
                        : Icons.download_for_offline_outlined,
                    size: 22,
                    color: iconColor,
                  ),
          ),
        ),
      ),
    );
  }
}

class _OfflineBoundaryBanner extends StatelessWidget {
  final String message;
  final VoidCallback onRecenter;

  const _OfflineBoundaryBanner({
    super.key,
    required this.message,
    required this.onRecenter,
  });

  @override
  Widget build(BuildContext context) {
    final bg = AppColors.warningContainer.withValues(alpha: 0.7);
    const fg = AppColors.warning;
    final border = AppColors.warning.withValues(alpha: 0.28);

    return MediaQuery.withClampedTextScaling(
      maxScaleFactor: 1.4,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: AppRadius.mdRadius,
          border: Border.all(color: border, width: 1),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Padding(
                  padding: EdgeInsets.only(top: 1),
                  child: Icon(
                    Icons.layers_clear_outlined,
                    size: 18,
                    color: fg,
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    message,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: AppTypography.bodyS.copyWith(
                      fontSize: 12.5,
                      height: 1.3,
                      color: fg,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                onPressed: onRecenter,
                style: TextButton.styleFrom(
                  foregroundColor: fg,
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  minimumSize: const Size(0, 28),
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.sm,
                    vertical: 2,
                  ),
                  textStyle: AppTypography.label.copyWith(
                    color: fg,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                child: const Text(
                  'Về Hạ Long',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
