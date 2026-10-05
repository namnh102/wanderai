import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import '../../../core/network/api_client.dart';
import '../data/place_model.dart';
import '../data/place_repository.dart';

// ── Default location: Hanoi ──
const _defaultCenter = LatLng(21.0285, 105.8542);

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
    bool clearSelectedPlace = false,
    bool clearCategory = false,
    bool clearSearch = false,
    bool clearError = false,
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
    );
  }
}

// ── Map Notifier ──
class MapNotifier extends StateNotifier<MapState> {
  final PlaceRepository _repo;

  MapNotifier(this._repo) : super(const MapState());

  /// Load nearby places from PostGIS.
  Future<void> loadNearby({LatLng? center, double? radiusKm}) async {
    final c = center ?? state.center;
    final r = radiusKm ?? state.radiusKm;

    state = state.copyWith(
      status: MapLoadingStatus.loading,
      center: c,
      radiusKm: r,
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

      final filtered = _applyClientFilters(places);

      state = state.copyWith(
        status: filtered.isEmpty ? MapLoadingStatus.empty : MapLoadingStatus.loaded,
        places: filtered,
      );
    } catch (e) {
      state = state.copyWith(
        status: MapLoadingStatus.error,
        errorMessage: 'Không thể tải địa điểm: ${e.toString().length > 80 ? e.toString().substring(0, 80) : e}',
      );
    }
  }

  /// Search places by text.
  Future<void> searchPlaces(String query) async {
    if (query.trim().isEmpty) {
      state = state.copyWith(clearSearch: true, clearSelectedPlace: true);
      return loadNearby();
    }

    state = state.copyWith(
      status: MapLoadingStatus.loading,
      searchQuery: query,
      clearError: true,
      clearSelectedPlace: true,
    );

    try {
      final places = await _repo.getPlaces(
        search: query,
        limit: 50,
        verifiedOnly: true,
        category: state.selectedCategory,
      );

      final withCoords = places.where((p) => p.hasCoordinates).toList();

      state = state.copyWith(
        status: withCoords.isEmpty ? MapLoadingStatus.empty : MapLoadingStatus.loaded,
        places: withCoords,
      );
    } catch (e) {
      state = state.copyWith(
        status: MapLoadingStatus.error,
        errorMessage: 'Lỗi tìm kiếm: $e',
      );
    }
  }

  /// Filter by category.
  void setCategory(String? category) {
    if (category == 'all') category = null;
    state = state.copyWith(
      selectedCategory: category,
      clearCategory: category == null,
      clearSelectedPlace: true,
    );

    // Re-apply filter or reload
    if (state.searchQuery != null && state.searchQuery!.isNotEmpty) {
      searchPlaces(state.searchQuery!);
    } else {
      loadNearby();
    }
  }

  /// Change radius and reload.
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

  /// Set user location as center.
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
