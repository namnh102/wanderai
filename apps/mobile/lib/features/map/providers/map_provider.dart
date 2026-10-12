import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import '../../../core/network/api_client.dart';
import '../data/destination_model.dart';
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
    bool clearSelectedPlace = false,
    bool clearCategory = false,
    bool clearSearch = false,
    bool clearError = false,
    bool clearActiveDestination = false,
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
    );
  }
}

// ── Map Notifier ──
class MapNotifier extends StateNotifier<MapState> {
  final PlaceRepository _repo;

  /// Request token: every operation that loads places takes a new one, and
  /// only the newest operation may write state. This makes late responses
  /// from superseded requests harmless.
  int _seq = 0;
  int _cameraSeq = 0;

  MapNotifier(this._repo) : super(const MapState());

  bool _stale(int token) => !mounted || token != _seq;

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
      await selectDestination(supportedDestinations.first.slug);
    }
  }

  /// Browse a supported destination: loads all its verified places (server
  /// side destination + category filter, paginated) and moves the camera to
  /// the backend destination coordinates.
  Future<void> selectDestination(String slug, {bool recenter = true}) async {
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
      if (dests.isEmpty) {
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
      );
    } catch (e) {
      if (_stale(token)) return;
      state = state.copyWith(
        status: MapLoadingStatus.error,
        errorMessage: e is DestinationResolutionException
            ? e.message
            : 'Không thể tải địa điểm. Vui lòng thử lại.',
      );
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
      // Leaving SEARCH: back to the last browsed destination.
      final slug = state.lastBrowseSlug;
      return selectDestination(slug ?? supportedDestinations.first.slug);
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

      final seen = <String>{};
      final withCoords = places
          .where((p) => p.hasCoordinates && seen.add(p.id))
          .toList();

      state = state.copyWith(
        status: withCoords.isEmpty ? MapLoadingStatus.empty : MapLoadingStatus.loaded,
        places: withCoords,
      );

      if (withCoords.length == 1) {
        final p = withCoords.single;
        final pt = LatLng(p.latitude!, p.longitude!);
        state = state.copyWith(selectedPlace: p);
        _emitCamera(pt, singleResultZoom);
      } else if (withCoords.length > 1) {
        final pts = withCoords
            .map((p) => LatLng(p.latitude!, p.longitude!))
            .toList();
        final lat = pts.map((p) => p.latitude).reduce((a, b) => a + b) / pts.length;
        final lng = pts.map((p) => p.longitude).reduce((a, b) => a + b) / pts.length;
        _emitCamera(LatLng(lat, lng), destinationZoom, fitPoints: pts);
      }
    } catch (e) {
      if (_stale(token)) return;
      state = state.copyWith(
        status: MapLoadingStatus.error,
        errorMessage: 'Không thể tìm kiếm. Vui lòng thử lại.',
      );
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

  List<PlaceModel> _applyClientFilters(List<PlaceModel> places) {
    var result = places.where((p) => p.hasCoordinates).toList();
    final cat = state.selectedCategory;
    if (cat != null && cat.isNotEmpty) {
      result = result
          .where((p) =>
              p.categoryName?.toLowerCase() == cat.toLowerCase())
          .toList();
    }
    return result;
  }
}

// ── Providers ──
final placeRepositoryProvider = Provider<PlaceRepository>((ref) {
  return PlaceRepository(ref.watch(apiClientProvider));
});

final mapProvider = StateNotifierProvider<MapNotifier, MapState>((ref) {
  return MapNotifier(ref.watch(placeRepositoryProvider));
});
