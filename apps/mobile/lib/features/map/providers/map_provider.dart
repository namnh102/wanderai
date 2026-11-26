import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import '../../../core/network/api_client.dart';
import '../data/destination_model.dart';
import '../data/offline_map_models.dart';
import '../data/offline_tile_downloader.dart';
import '../data/offline_tile_store.dart';
import '../data/place_model.dart';
import '../data/place_repository.dart';

// ── Default location: Hanoi ──
const _defaultCenter = LatLng(21.0285, 105.8542);

/// Zoom used when the camera is sent to a destination (city overview).
const destinationZoom = 12.0;

/// Zoom used when a single search result is shown.
const singleResultZoom = 16.0;

// ── Category definitions matching backend place_categories ──
class PlaceCategory {
  final String key;
  final String label;
  final String icon; // Material icon name from DB
  final String color;

  const PlaceCategory(this.key, this.label, this.icon, this.color);
}

const mapCategories = [
  PlaceCategory('all', 'Tất cả', 'category', '#00685F'),
  PlaceCategory('attraction', 'Tham quan', 'attractions', '#9C27B0'),
  PlaceCategory('restaurant', 'Nhà hàng', 'restaurant', '#FF5722'),
  PlaceCategory('hotel', 'Khách sạn', 'hotel', '#2196F3'),
  PlaceCategory('culture', 'Văn hóa', 'museum', '#FF9800'),
  PlaceCategory('beach', 'Biển', 'beach_access', '#00BCD4'),
  PlaceCategory('nature', 'Thiên nhiên', 'park', '#8BC34A'),
  PlaceCategory('entertainment', 'Giải trí', 'celebration', '#E91E63'),
  PlaceCategory('cafe', 'Cà phê', 'local_cafe', '#795548'),
];

// ── Radius options (km) ──
const radiusOptions = [1.0, 5.0, 10.0, 25.0];

// ── Map State ──
enum MapLoadingStatus { initial, loading, loaded, empty, error }

/// How the Map currently decides which places to show.
enum MapMode {
  /// A supported destination is selected and all its verified places shown.
  destination,

  /// Global text search (not limited by destination).
  search,

  /// Places around the user's location (after "Vị trí của tôi").
  nearby,
}

/// A one-shot camera instruction. [seq] is strictly increasing so listeners
/// can tell a new request from a re-delivered one; the screen applies it from
/// a listener (never from `build()`).
class MapCameraRequest {
  final int seq;
  final LatLng center;
  final double zoom;

  /// When it holds 2+ points the camera must fit all of them (with padding).
  final List<LatLng> fitPoints;

  const MapCameraRequest({
    required this.seq,
    required this.center,
    required this.zoom,
    this.fitPoints = const [],
  });
}

class MapState {
  final MapLoadingStatus status;
  final List<PlaceModel> places;
  final LatLng center;
  final double radiusKm;
  final String? selectedCategory; // null = all
  final String? searchQuery;
  final PlaceModel? selectedPlace;
  final String? errorMessage;
  final bool useLocation;

  final MapMode mode;

  /// Supported destinations resolved from `GET /destinations`, by slug.
  final Map<String, DestinationModel> destinations;

  /// Highlighted destination (null in SEARCH / NEARBY: neutral state).
  final String? activeDestinationSlug;

  /// Last destination browsed; restored when search is cleared.
  final String? lastBrowseSlug;

  final MapCameraRequest? cameraRequest;

  // ── Offline map state (W09-C) ──
  final OfflineRegionManifest? cachedHalongRegion;
  final bool isOfflineMode;
  final bool isDownloadingOffline;
  final OfflineDownloadProgress? offlineProgress;
  final String? offlineError;
  final int tileLayerResetEpoch;

  const MapState({
    this.status = MapLoadingStatus.initial,
    this.places = const [],
    this.center = _defaultCenter,
    this.radiusKm = 10.0,
    this.selectedCategory,
    this.searchQuery,
    this.selectedPlace,
    this.errorMessage,
    this.useLocation = false,
    this.mode = MapMode.destination,
    this.destinations = const {},
    this.activeDestinationSlug,
    this.lastBrowseSlug,
    this.cameraRequest,
    this.cachedHalongRegion,
    this.isOfflineMode = false,
    this.isDownloadingOffline = false,
    this.offlineProgress,
    this.offlineError,
    this.tileLayerResetEpoch = 0,
  });

  MapState copyWith({
    MapLoadingStatus? status,
    List<PlaceModel>? places,
    LatLng? center,
    double? radiusKm,
    String? selectedCategory,
    String? searchQuery,
    PlaceModel? selectedPlace,
    String? errorMessage,
    bool? useLocation,
    MapMode? mode,
    Map<String, DestinationModel>? destinations,
    String? activeDestinationSlug,
    String? lastBrowseSlug,
    MapCameraRequest? cameraRequest,
    OfflineRegionManifest? cachedHalongRegion,
    bool? isOfflineMode,
    bool? isDownloadingOffline,
    OfflineDownloadProgress? offlineProgress,
    String? offlineError,
    int? tileLayerResetEpoch,
    bool clearSelectedPlace = false,
    bool clearCategory = false,
    bool clearSearch = false,
    bool clearError = false,
    bool clearActiveDestination = false,
    bool clearCachedHalongRegion = false,
    bool clearOfflineProgress = false,
    bool clearOfflineError = false,
  }) {
    return MapState(
      status: status ?? this.status,
      places: places ?? this.places,
      center: center ?? this.center,
      radiusKm: radiusKm ?? this.radiusKm,
      selectedCategory:
          clearCategory ? null : (selectedCategory ?? this.selectedCategory),
      searchQuery: clearSearch ? null : (searchQuery ?? this.searchQuery),
      selectedPlace:
          clearSelectedPlace ? null : (selectedPlace ?? this.selectedPlace),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      useLocation: useLocation ?? this.useLocation,
      mode: mode ?? this.mode,
      destinations: destinations ?? this.destinations,
      activeDestinationSlug: clearActiveDestination
          ? null
          : (activeDestinationSlug ?? this.activeDestinationSlug),
      lastBrowseSlug: lastBrowseSlug ?? this.lastBrowseSlug,
      cameraRequest: cameraRequest ?? this.cameraRequest,
      cachedHalongRegion: clearCachedHalongRegion
          ? null
          : (cachedHalongRegion ?? this.cachedHalongRegion),
      isOfflineMode: isOfflineMode ?? this.isOfflineMode,
      isDownloadingOffline:
          isDownloadingOffline ?? this.isDownloadingOffline,
      offlineProgress: clearOfflineProgress
          ? null
          : (offlineProgress ?? this.offlineProgress),
      offlineError:
          clearOfflineError ? null : (offlineError ?? this.offlineError),
      tileLayerResetEpoch: tileLayerResetEpoch ?? this.tileLayerResetEpoch,
    );
  }
}

// ── Map Notifier ──
class MapNotifier extends StateNotifier<MapState> {
  final PlaceRepository _repo;
  final OfflineTileStore? _offlineStore;
  final OfflineTileDownloader? _offlineDownloader;

  /// Request token: every operation that loads places takes a new one, and
  /// only the newest operation may write state. This makes late responses
  /// from superseded requests harmless.
  int _seq = 0;
  int _cameraSeq = 0;
  bool _cancelDownloadRequested = false;
  int _offlineEpoch = 0;
  Future<OfflineDownloadResult?>? _activeDownloadFuture;

  MapNotifier(
    this._repo, {
    OfflineTileStore? offlineStore,
    OfflineTileDownloader? offlineDownloader,
  })  : _offlineStore = offlineStore,
        _offlineDownloader = offlineDownloader,
        super(const MapState());

  bool _stale(int token) => !mounted || token != _seq;

  bool _isNetworkError(Object error) {
    if (error is DestinationResolutionException) return false;
    if (error is SocketException) return true;
    if (error is DioException) {
      return error.response == null &&
          (error.type == DioExceptionType.connectionError ||
              error.type == DioExceptionType.connectionTimeout ||
              error.type == DioExceptionType.receiveTimeout ||
              error.type == DioExceptionType.sendTimeout ||
              error.type == DioExceptionType.unknown);
    }
    return false;
  }

  void _emitCamera(LatLng center, double zoom,
      {List<LatLng> fitPoints = const []}) {
    state = state.copyWith(
      center: center,
      cameraRequest: MapCameraRequest(
        seq: ++_cameraSeq,
        center: center,
        zoom: zoom,
        fitPoints: fitPoints,
      ),
    );
  }

  /// First open of the Map: no-op if places were already loaded.
  Future<void> ensureInitialized() async {
    if (state.status == MapLoadingStatus.initial ||
        (state.status == MapLoadingStatus.error &&
            state.destinations.isEmpty)) {
      // Load cached region metadata in parallel so online startup never stalls
      // waiting on platform directory resolution.
      final cacheFuture = refreshOfflineCache();
      await _selectDestinationInternal(
        supportedDestinations.first.slug,
        recenter: true,
        allowHalongOfflineFallback: true,
      );
      await cacheFuture;
    }
  }

  /// Loads cached Hạ Long offline manifest metadata from disk if present.
  Future<OfflineRegionManifest?> refreshOfflineCache() async {
    final store = _offlineStore;
    if (store == null) return null;
    final cached = await store.loadManifest(halongOfflineRegionPreset.regionId);
    if (!mounted) return cached;
    if (cached != null && state.cachedHalongRegion == null) {
      state = state.copyWith(cachedHalongRegion: cached);
    }
    return cached;
  }

  /// Browse a supported destination: loads all its verified places (server
  /// side destination + category filter, paginated) and moves the camera to
  /// the backend destination coordinates.
  Future<void> selectDestination(String slug, {bool recenter = true}) {
    return _selectDestinationInternal(
      slug,
      recenter: recenter,
      allowHalongOfflineFallback: slug == halongOfflineRegionPreset.destinationSlug,
    );
  }

  Future<void> _selectDestinationInternal(
    String slug, {
    required bool recenter,
    required bool allowHalongOfflineFallback,
  }) async {
    final token = ++_seq;
    state = state.copyWith(
      status: MapLoadingStatus.loading,
      mode: MapMode.destination,
      activeDestinationSlug: slug,
      lastBrowseSlug: slug,
      places: const [],
      clearSearch: true,
      clearSelectedPlace: true,
      clearError: true,
    );

    try {
      var dests = state.destinations;
      if (dests.length < supportedDestinations.length) {
        final all = await _repo.getDestinations();
        if (_stale(token)) return;
        dests = resolveSupportedDestinations(all);
        state = state.copyWith(destinations: dests);
      }
      final dest = dests[slug];
      if (dest == null) {
        throw DestinationResolutionException(
            'Điểm đến "$slug" không được hỗ trợ.');
      }
      if (recenter) _emitCamera(dest.center, destinationZoom);

      final places = await _repo.getAllPlacesForDestination(
        destinationId: dest.id,
        category: state.selectedCategory,
      );
      if (_stale(token)) return;
      final withCoords = places.where((p) => p.hasCoordinates).toList();
      state = state.copyWith(
        status:
            withCoords.isEmpty ? MapLoadingStatus.empty : MapLoadingStatus.loaded,
        places: withCoords,
        isOfflineMode: false,
      );
    } catch (e) {
      if (_stale(token)) return;
      if (_isNetworkError(e) && _offlineStore != null) {
        final cached = state.cachedHalongRegion ??
            await _offlineStore!
                .loadManifest(halongOfflineRegionPreset.regionId);
        if (_stale(token)) return;
        if (cached != null) {
          if (slug == cached.destinationSlug || allowHalongOfflineFallback) {
            _activateOfflineManifest(cached, recenter: recenter);
            return;
          }
          state = state.copyWith(
            status: MapLoadingStatus.error,
            isOfflineMode: true,
            cachedHalongRegion: cached,
            errorMessage:
                'Chưa có dữ liệu ngoại tuyến cho khu vực này. Hãy mở vùng Hạ Long đã tải.',
          );
          return;
        }
      }
      state = state.copyWith(
        status: MapLoadingStatus.error,
        errorMessage: e is DestinationResolutionException
            ? e.message
            : 'Không thể tải địa điểm. Vui lòng thử lại.',
      );
    }
  }

  void _activateOfflineManifest(
    OfflineRegionManifest cached, {
    required bool recenter,
  }) {
    final dest = cached.destination ??
        DestinationModel(
          id: cached.regionId,
          slug: cached.destinationSlug,
          name: 'Hạ Long',
          latitude: cached.bbox.center.latitude,
          longitude: cached.bbox.center.longitude,
        );
    final filtered = _applyClientFilters(cached.places);
    state = state.copyWith(
      status: filtered.isEmpty ? MapLoadingStatus.empty : MapLoadingStatus.loaded,
      mode: MapMode.destination,
      destinations: {...state.destinations, cached.destinationSlug: dest},
      activeDestinationSlug: cached.destinationSlug,
      lastBrowseSlug: cached.destinationSlug,
      places: filtered,
      isOfflineMode: true,
      cachedHalongRegion: cached,
      clearError: true,
    );
    if (recenter) {
      _emitCamera(cached.bbox.center, cached.recommendedInitialZoom);
    }
  }

  /// Load nearby places from PostGIS (NEARBY mode).
  Future<void> loadNearby({LatLng? center, double? radiusKm}) async {
    final token = ++_seq;
    final c = center ?? state.center;
    final r = radiusKm ?? state.radiusKm;

    state = state.copyWith(
      status: MapLoadingStatus.loading,
      mode: MapMode.nearby,
      center: c,
      radiusKm: r,
      clearActiveDestination: true,
      clearSearch: true,
      clearError: true,
      clearSelectedPlace: true,
    );

    try {
      final places = await _repo.getNearby(
        lat: c.latitude,
        lng: c.longitude,
        radiusKm: r,
        limit: 100,
        verifiedOnly: true,
      );
      if (_stale(token)) return;

      final filtered = _applyClientFilters(places);

      state = state.copyWith(
        status: filtered.isEmpty ? MapLoadingStatus.empty : MapLoadingStatus.loaded,
        places: filtered,
      );
    } catch (e) {
      if (_stale(token)) return;
      state = state.copyWith(
        status: MapLoadingStatus.error,
        errorMessage: 'Không thể tải địa điểm: ${e.toString().length > 80 ? e.toString().substring(0, 80) : e}',
      );
    }
  }

  /// Search places globally by text (not limited by destination).
  ///
  /// Camera policy: 0 results → untouched; 1 result → centre on it and
  /// select it; 2+ results → fit all markers.
  Future<void> searchPlaces(String query) async {
    final q = query.trim();
    if (q.isEmpty) {
      state = state.copyWith(clearSearch: true, clearSelectedPlace: true);
      if (state.mode != MapMode.search) return;
      if (state.isOfflineMode && state.cachedHalongRegion != null) {
        _activateOfflineManifest(state.cachedHalongRegion!, recenter: true);
        return;
      }
      // Leaving SEARCH: back to the last browsed destination.
      final slug = state.lastBrowseSlug;
      return selectDestination(slug ?? supportedDestinations.first.slug);
    }

    if (state.isOfflineMode && state.cachedHalongRegion != null) {
      _searchOfflinePlaces(q, state.cachedHalongRegion!);
      return;
    }

    final token = ++_seq;
    state = state.copyWith(
      status: MapLoadingStatus.loading,
      mode: MapMode.search,
      searchQuery: q,
      places: const [],
      clearActiveDestination: true,
      clearError: true,
      clearSelectedPlace: true,
    );

    try {
      final places = await _repo.getPlaces(
        search: q,
        limit: placesMaxPageSize,
        verifiedOnly: true,
        category: state.selectedCategory,
      );
      if (_stale(token)) return;

      _applySearchResults(places);
    } catch (e) {
      if (_stale(token)) return;
      if (_isNetworkError(e) && state.cachedHalongRegion != null) {
        _searchOfflinePlaces(q, state.cachedHalongRegion!);
        return;
      }
      state = state.copyWith(
        status: MapLoadingStatus.error,
        errorMessage: 'Không thể tìm kiếm. Vui lòng thử lại.',
      );
    }
  }

  static String foldVietnameseSearch(String input) {
    final lower = input.toLowerCase();
    final buf = StringBuffer();
    for (final rune in lower.runes) {
      // Skip combining diacritical marks for NFD-encoded strings.
      if (rune >= 0x0300 && rune <= 0x036F) continue;
      final ch = String.fromCharCode(rune);
      buf.write(_vietnameseFoldMap[ch] ?? ch);
    }
    return buf.toString();
  }

  static const Map<String, String> _vietnameseFoldMap = {
    'à': 'a', 'á': 'a', 'ạ': 'a', 'ả': 'a', 'ã': 'a',
    'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ậ': 'a', 'ẩ': 'a', 'ẫ': 'a',
    'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ặ': 'a', 'ẳ': 'a', 'ẵ': 'a',
    'è': 'e', 'é': 'e', 'ẹ': 'e', 'ẻ': 'e', 'ẽ': 'e',
    'ê': 'e', 'ề': 'e', 'ế': 'e', 'ệ': 'e', 'ể': 'e', 'ễ': 'e',
    'ì': 'i', 'í': 'i', 'ị': 'i', 'ỉ': 'i', 'ĩ': 'i',
    'ò': 'o', 'ó': 'o', 'ọ': 'o', 'ỏ': 'o', 'õ': 'o',
    'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ộ': 'o', 'ổ': 'o', 'ỗ': 'o',
    'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ợ': 'o', 'ở': 'o', 'ỡ': 'o',
    'ù': 'u', 'ú': 'u', 'ụ': 'u', 'ủ': 'u', 'ũ': 'u',
    'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ự': 'u', 'ử': 'u', 'ữ': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỵ': 'y', 'ỷ': 'y', 'ỹ': 'y',
    'đ': 'd',
  };

  void _searchOfflinePlaces(String q, OfflineRegionManifest cached) {
    final needle = foldVietnameseSearch(q);
    final matches = _applyClientFilters(cached.places).where((p) {
      final name = foldVietnameseSearch(p.name);
      final nameEn = foldVietnameseSearch(p.nameEn ?? '');
      final address = foldVietnameseSearch(p.address ?? '');
      final cat = foldVietnameseSearch(p.categoryName ?? '');
      return name.contains(needle) ||
          nameEn.contains(needle) ||
          address.contains(needle) ||
          cat.contains(needle);
    }).toList();

    state = state.copyWith(
      mode: MapMode.search,
      searchQuery: q,
      isOfflineMode: true,
      clearActiveDestination: true,
      clearError: true,
      clearSelectedPlace: true,
    );
    _applySearchResults(matches);
  }

  void _applySearchResults(List<PlaceModel> places) {
    final seen = <String>{};
    final withCoords =
        places.where((p) => p.hasCoordinates && seen.add(p.id)).toList();

    state = state.copyWith(
      status:
          withCoords.isEmpty ? MapLoadingStatus.empty : MapLoadingStatus.loaded,
      places: withCoords,
    );

    if (withCoords.length == 1) {
      final p = withCoords.single;
      final pt = LatLng(p.latitude!, p.longitude!);
      state = state.copyWith(selectedPlace: p);
      _emitCamera(pt, singleResultZoom);
    } else if (withCoords.length > 1) {
      final pts =
          withCoords.map((p) => LatLng(p.latitude!, p.longitude!)).toList();
      final lat =
          pts.map((p) => p.latitude).reduce((a, b) => a + b) / pts.length;
      final lng =
          pts.map((p) => p.longitude).reduce((a, b) => a + b) / pts.length;
      _emitCamera(LatLng(lat, lng), destinationZoom, fitPoints: pts);
    }
  }

  /// Filter by category (re-queries the current mode; never keeps stale rows).
  void setCategory(String? category) {
    if (category == 'all') category = null;
    state = state.copyWith(
      selectedCategory: category,
      clearCategory: category == null,
      clearSelectedPlace: true,
    );

    switch (state.mode) {
      case MapMode.search:
        final q = state.searchQuery;
        if (q != null && q.isNotEmpty) {
          searchPlaces(q);
        } else {
          loadNearby();
        }
        break;
      case MapMode.nearby:
        loadNearby();
        break;
      case MapMode.destination:
        if (state.isOfflineMode && state.cachedHalongRegion != null) {
          _activateOfflineManifest(state.cachedHalongRegion!, recenter: false);
          return;
        }
        selectDestination(
          state.activeDestinationSlug ??
              state.lastBrowseSlug ??
              supportedDestinations.first.slug,
          recenter: false,
        );
        break;
    }
  }

  /// Retry the operation that failed, without silently switching mode.
  Future<void> retry() {
    switch (state.mode) {
      case MapMode.search:
        final q = state.searchQuery;
        if (q != null && q.isNotEmpty) return searchPlaces(q);
        return selectDestination(
            state.lastBrowseSlug ?? supportedDestinations.first.slug);
      case MapMode.nearby:
        return loadNearby();
      case MapMode.destination:
        return selectDestination(
            state.activeDestinationSlug ??
                state.lastBrowseSlug ??
                supportedDestinations.first.slug);
    }
  }

  /// Downloads the Hạ Long offline map region (`z=12..17`) and POIs to disk.
  Future<OfflineDownloadResult?> downloadHalongOfflineRegion() {
    final downloader = _offlineDownloader;
    if (downloader == null) {
      state = state.copyWith(
        offlineError: 'Bộ tải bản đồ ngoại tuyến chưa sẵn sàng.',
      );
      return Future.value(null);
    }
    if (state.isDownloadingOffline && _activeDownloadFuture != null) {
      return _activeDownloadFuture!;
    }

    final epoch = ++_offlineEpoch;
    _cancelDownloadRequested = false;
    state = state.copyWith(
      isDownloadingOffline: true,
      clearOfflineError: true,
      clearOfflineProgress: true,
    );

    final future = _runHalongOfflineDownload(downloader, epoch);
    _activeDownloadFuture = future;
    return future;
  }

  Future<OfflineDownloadResult?> _runHalongOfflineDownload(
    OfflineTileDownloader downloader,
    int epoch,
  ) async {
    try {
      final result = await downloader.downloadRegion(
        preset: halongOfflineRegionPreset,
        skipExisting: true,
        isCancelled: () =>
            _cancelDownloadRequested || !mounted || epoch != _offlineEpoch,
        onProgress: (progress) {
          if (!mounted || epoch != _offlineEpoch) return;
          state = state.copyWith(offlineProgress: progress);
        },
      );
      if (!mounted || epoch != _offlineEpoch) return result;
      state = state.copyWith(
        isDownloadingOffline: false,
        cachedHalongRegion: result.manifest,
        tileLayerResetEpoch: state.tileLayerResetEpoch + 1,
        offlineError: result.failedTiles > 0 && result.manifest.tileCount == 0
            ? 'Không thể tải mảnh bản đồ ngoại tuyến.'
            : null,
      );
      return result;
    } catch (_) {
      if (!mounted || epoch != _offlineEpoch) return null;
      state = state.copyWith(
        isDownloadingOffline: false,
        offlineError: 'Không thể tải bản đồ ngoại tuyến. Vui lòng thử lại.',
      );
      return null;
    } finally {
      if (epoch == _offlineEpoch) {
        _activeDownloadFuture = null;
      }
    }
  }

  void cancelOfflineDownload() {
    _cancelDownloadRequested = true;
  }

  /// Deletes the cached Hạ Long offline region from disk.
  Future<void> deleteHalongOfflineRegion() async {
    final deleteEpoch = ++_offlineEpoch;
    _cancelDownloadRequested = true;
    final inFlight = _activeDownloadFuture;
    if (inFlight != null) {
      try {
        await inFlight;
      } catch (_) {
        // Ignore download failures when cancelling for deletion.
      }
      if (identical(_activeDownloadFuture, inFlight)) {
        _activeDownloadFuture = null;
      }
    }
    if (!mounted || deleteEpoch != _offlineEpoch) return;
    await _offlineStore?.deleteRegion(halongOfflineRegionPreset.regionId);
    if (!mounted || deleteEpoch != _offlineEpoch) return;
    state = state.copyWith(
      isDownloadingOffline: false,
      clearCachedHalongRegion: true,
      clearOfflineProgress: true,
      clearOfflineError: true,
      isOfflineMode: false,
      tileLayerResetEpoch: state.tileLayerResetEpoch + 1,
    );
  }

  /// Centers the camera on the downloaded Hạ Long offline bounding box.
  void recenterToOfflineRegion() {
    final region = state.cachedHalongRegion;
    final targetCenter =
        region?.bbox.center ?? halongOfflineRegionPreset.bounds.center;
    final targetZoom = region?.recommendedInitialZoom ??
        halongOfflineRegionPreset.recommendedInitialZoom;
    if (state.isOfflineMode &&
        region != null &&
        state.activeDestinationSlug != region.destinationSlug) {
      _activateOfflineManifest(region, recenter: true);
      return;
    }
    _emitCamera(targetCenter, targetZoom);
  }

  /// Change radius and reload (NEARBY mode).
  void setRadius(double radiusKm) {
    loadNearby(radiusKm: radiusKm);
  }

  /// Move map center and reload nearby.
  void moveCenter(LatLng center) {
    loadNearby(center: center);
  }

  /// Select a place (show preview).
  void selectPlace(PlaceModel place) {
    state = state.copyWith(selectedPlace: place);
  }

  /// Deselect place.
  void deselectPlace() {
    state = state.copyWith(clearSelectedPlace: true);
  }

  /// Set user location as center: enters NEARBY mode.
  void setUserLocation(LatLng location) {
    state = state.copyWith(useLocation: true);
    loadNearby(center: location);
  }

  bool _matchesCategory(String? placeCategory, String selectedCategory) {
    final placeCat = placeCategory?.trim().toLowerCase();
    if (placeCat == null || placeCat.isEmpty) return false;
    final selected = selectedCategory.trim().toLowerCase();
    if (placeCat == selected) return true;
    if (selected == 'culture') {
      return const {
        'culture',
        'văn hóa',
        'museum',
        'bảo tàng',
        'temple',
        'pagoda',
      }.contains(placeCat);
    }
    if (selected == 'nature') {
      return const {
        'nature',
        'thiên nhiên',
        'park',
        'công viên',
      }.contains(placeCat);
    }
    return false;
  }

  List<PlaceModel> _applyClientFilters(List<PlaceModel> places) {
    var result = places.where((p) => p.hasCoordinates).toList();
    final cat = state.selectedCategory;
    if (cat != null && cat.isNotEmpty) {
      result = result
          .where((p) => _matchesCategory(p.categoryName, cat))
          .toList();
    }
    return result;
  }
}

// ── Providers ──
final offlineTileStoreProvider = Provider<OfflineTileStore>((ref) {
  return OfflineTileStore();
});

final offlineTileDioProvider = Provider<Dio>((ref) {
  return Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
    ),
  );
});

final offlineTileDownloaderProvider = Provider<OfflineTileDownloader>((ref) {
  return OfflineTileDownloader(
    store: ref.watch(offlineTileStoreProvider),
    tileDio: ref.watch(offlineTileDioProvider),
    placeRepository: ref.watch(placeRepositoryProvider),
  );
});

final placeRepositoryProvider = Provider<PlaceRepository>((ref) {
  return PlaceRepository(ref.watch(apiClientProvider));
});

final mapProvider = StateNotifierProvider<MapNotifier, MapState>((ref) {
  return MapNotifier(
    ref.watch(placeRepositoryProvider),
    offlineStore: ref.watch(offlineTileStoreProvider),
    offlineDownloader: ref.watch(offlineTileDownloaderProvider),
  );
});
