import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import '../../../core/network/api_client.dart';
import '../../map/data/place_model.dart';
import '../../map/data/place_repository.dart';
import '../../map/providers/map_provider.dart';
import '../data/home_models.dart';

class HomeState {
  final bool isLoading;
  final List<HomeDestinationItem> destinations;
  final List<PlaceModel> featuredPlaces;
  final List<PlaceModel> trendingPlaces;
  final List<PlaceModel> nearbyPlaces;
  final bool isNearbyLoading;
  final bool hasNearbyLoaded;
  final String? userDisplayName;
  final List<String> userInterests;
  final HomeRegionFilter selectedRegion;
  final bool showAllDestinations;
  final String? errorMessage;
  final bool isOfflineError;
  final String? partialBannerMessage;

  const HomeState({
    this.isLoading = true,
    this.destinations = const [],
    this.featuredPlaces = const [],
    this.trendingPlaces = const [],
    this.nearbyPlaces = const [],
    this.isNearbyLoading = false,
    this.hasNearbyLoaded = false,
    this.userDisplayName,
    this.userInterests = const [],
    this.selectedRegion = HomeRegionFilter.all,
    this.showAllDestinations = false,
    this.errorMessage,
    this.isOfflineError = false,
    this.partialBannerMessage,
  });

  List<HomeDestinationItem> get filteredDestinations {
    final regionKey = selectedRegion.apiValue;
    if (regionKey == null) return destinations;
    return destinations
        .where((d) => d.region?.toLowerCase() == regionKey)
        .toList();
  }

  HomeState copyWith({
    bool? isLoading,
    List<HomeDestinationItem>? destinations,
    List<PlaceModel>? featuredPlaces,
    List<PlaceModel>? trendingPlaces,
    List<PlaceModel>? nearbyPlaces,
    bool? isNearbyLoading,
    bool? hasNearbyLoaded,
    String? userDisplayName,
    List<String>? userInterests,
    HomeRegionFilter? selectedRegion,
    bool? showAllDestinations,
    String? errorMessage,
    bool? isOfflineError,
    String? partialBannerMessage,
    bool clearError = false,
    bool clearPartialBanner = false,
  }) {
    return HomeState(
      isLoading: isLoading ?? this.isLoading,
      destinations: destinations ?? this.destinations,
      featuredPlaces: featuredPlaces ?? this.featuredPlaces,
      trendingPlaces: trendingPlaces ?? this.trendingPlaces,
      nearbyPlaces: nearbyPlaces ?? this.nearbyPlaces,
      isNearbyLoading: isNearbyLoading ?? this.isNearbyLoading,
      hasNearbyLoaded: hasNearbyLoaded ?? this.hasNearbyLoaded,
      userDisplayName: userDisplayName ?? this.userDisplayName,
      userInterests: userInterests ?? this.userInterests,
      selectedRegion: selectedRegion ?? this.selectedRegion,
      showAllDestinations: showAllDestinations ?? this.showAllDestinations,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      isOfflineError: isOfflineError ?? this.isOfflineError,
      partialBannerMessage: clearPartialBanner
          ? null
          : (partialBannerMessage ?? this.partialBannerMessage),
    );
  }
}

class HomeNotifier extends StateNotifier<HomeState> {
  final Dio _dio;
  final PlaceRepository _placeRepo;
  int _loadSeq = 0;
  int _nearbySeq = 0;

  HomeNotifier(this._dio, this._placeRepo, {bool autoLoad = true})
      : super(const HomeState()) {
    if (autoLoad) {
      load();
    }
  }

  bool _isConnectionFailure(DioException e) {
    return e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout;
  }

  String _formatDioError(DioException e) {
    if (_isConnectionFailure(e)) {
      return 'Không có kết nối mạng hoặc không thể chạm tới máy chủ. Vui lòng kiểm tra kết nối và thử lại.';
    }
    final status = e.response?.statusCode;
    if (status == 401) {
      return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
    }
    return 'Không thể tải dữ liệu khám phá (mã lỗi ${status ?? 'mạng'}). Vui lòng thử lại.';
  }

  Future<void> load({LatLng? userPosition}) async {
    final seq = ++_loadSeq;
    state = state.copyWith(
      isLoading: state.destinations.isEmpty,
      clearError: true,
      clearPartialBanner: true,
      isOfflineError: false,
    );

    try {
      final destFuture = _dio.get('/destinations', queryParameters: {'limit': 50});
      final placesFuture = _loadFeaturedPlacesSoft();
      final trendingFuture = _loadTrendingSoft();
      final profileFuture = _loadProfileSoft();

      final destResp = await destFuture;
      if (!mounted || seq != _loadSeq) return;

      final rawData = destResp.data;
      final rawItems = rawData is Map ? (rawData['data']?['items'] as List? ?? []) : const [];
      final parsedDestinations = rawItems
          .whereType<Map<String, dynamic>>()
          .map(HomeDestinationItem.fromJson)
          .toList()
        ..sort((a, b) {
          if (a.isPopular != b.isPopular) return a.isPopular ? -1 : 1;
          return b.placeCount.compareTo(a.placeCount);
        });

      final placesResult = await placesFuture;
      final trendingResult = await trendingFuture;
      final profileResult = await profileFuture;
      if (!mounted || seq != _loadSeq) return;

      state = state.copyWith(
        isLoading: false,
        destinations: parsedDestinations,
        featuredPlaces: placesResult.$1,
        trendingPlaces: trendingResult,
        partialBannerMessage: placesResult.$2,
        userDisplayName: profileResult.$1,
        userInterests: profileResult.$2,
        clearError: true,
        isOfflineError: false,
      );

      if (userPosition != null) {
        await loadNearby(userPosition);
      }
    } on DioException catch (e) {
      if (!mounted || seq != _loadSeq) return;
      final offline = _isConnectionFailure(e);
      final msg = _formatDioError(e);
      if (state.destinations.isNotEmpty) {
        state = state.copyWith(
          isLoading: false,
          isOfflineError: offline,
          partialBannerMessage: msg,
        );
      } else {
        state = state.copyWith(
          isLoading: false,
          errorMessage: msg,
          isOfflineError: offline,
        );
      }
    } catch (_) {
      if (!mounted || seq != _loadSeq) return;
      const msg = 'Đã xảy ra lỗi không mong muốn khi tải dữ liệu khám phá.';
      if (state.destinations.isNotEmpty) {
        state = state.copyWith(
          isLoading: false,
          partialBannerMessage: msg,
        );
      } else {
        state = state.copyWith(
          isLoading: false,
          errorMessage: msg,
        );
      }
    }
  }

  Future<List<PlaceModel>> _loadTrendingSoft() async {
    try {
      final resp = await _dio.get('/places/trending', queryParameters: {'limit': 6});
      final raw = resp.data;
      final inner = raw is Map ? (raw['data'] ?? raw) : raw;
      final items = inner is Map ? (inner['items'] as List? ?? const []) : const [];
      return items
          .whereType<Map<String, dynamic>>()
          .map(PlaceModel.fromJson)
          .toList();
    } catch (_) {
      return const <PlaceModel>[];
    }
  }

  Future<(List<PlaceModel>, String?)> _loadFeaturedPlacesSoft() async {
    try {
      final places = await _placeRepo.getPlaces(
        page: 1,
        limit: 8,
        verifiedOnly: true,
      );
      return (places, null);
    } on DioException catch (e) {
      if (_isConnectionFailure(e)) {
        return (<PlaceModel>[], 'Kết nối không ổn định, chưa tải được địa điểm xác minh.');
      }
      return (<PlaceModel>[], null);
    } catch (_) {
      return (<PlaceModel>[], null);
    }
  }

  Future<(String?, List<String>)> _loadProfileSoft() async {
    try {
      final resp = await _dio.get('/users/me');
      final data = resp.data;
      if (data is! Map || data['data'] is! Map) {
        return (null, const <String>[]);
      }
      final userMap = data['data'] as Map<String, dynamic>;
      final profile = userMap['profile'];
      final rawName = profile is Map ? (profile['displayName'] as String?) : null;
      final trimmedName = rawName?.trim();
      final prefs = userMap['preferences'];
      final rawInterests = prefs is Map && prefs['interests'] is List
          ? List<String>.from((prefs['interests'] as List).map((e) => e.toString()))
          : const <String>[];
      return (
        (trimmedName != null && trimmedName.isNotEmpty) ? trimmedName : null,
        rawInterests,
      );
    } catch (_) {
      return (null, const <String>[]);
    }
  }

  Future<void> loadNearby(LatLng position) async {
    final seq = ++_nearbySeq;
    state = state.copyWith(isNearbyLoading: true);
    try {
      final nearby = await _placeRepo.getNearby(
        lat: position.latitude,
        lng: position.longitude,
        radiusKm: 10,
        limit: 6,
        verifiedOnly: true,
      );
      if (!mounted || seq != _nearbySeq) return;
      state = state.copyWith(
        nearbyPlaces: nearby,
        isNearbyLoading: false,
        hasNearbyLoaded: true,
      );
    } catch (_) {
      if (!mounted || seq != _nearbySeq) return;
      state = state.copyWith(
        isNearbyLoading: false,
        hasNearbyLoaded: true,
        partialBannerMessage: 'Không thể cập nhật danh sách địa điểm gần bạn lúc này.',
      );
    }
  }

  /// Reset session-scoped home state on logout without triggering unauthenticated fetches.
  void resetForLogout() {
    _loadSeq++;
    _nearbySeq++;
    state = const HomeState(isLoading: false);
  }

  void setRegion(HomeRegionFilter region) {
    if (state.selectedRegion == region) return;
    state = state.copyWith(selectedRegion: region);
  }

  void toggleShowAllDestinations() {
    state = state.copyWith(showAllDestinations: !state.showAllDestinations);
  }
}

final homeProvider =
    StateNotifierProvider.autoDispose<HomeNotifier, HomeState>((ref) {
  final dio = ref.watch(apiClientProvider);
  final placeRepo = ref.watch(placeRepositoryProvider);
  return HomeNotifier(dio, placeRepo);
});
