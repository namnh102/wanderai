import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/trip_models.dart';
import '../data/trip_repository.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_error.dart';

class TripListState {
  final List<TripModel> trips;
  final bool isLoading;
  final String? errorMessage;
  final bool isOfflineError;

  const TripListState({
    this.trips = const [],
    this.isLoading = false,
    this.errorMessage,
    this.isOfflineError = false,
  });

  bool get isEmpty => !isLoading && trips.isEmpty && errorMessage == null;

  TripListState copyWith({
    List<TripModel>? trips,
    bool? isLoading,
    String? errorMessage,
    bool? isOfflineError,
    bool clearError = false,
  }) {
    return TripListState(
      trips: trips ?? this.trips,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      isOfflineError: clearError ? false : (isOfflineError ?? this.isOfflineError),
    );
  }
}

class TripListNotifier extends StateNotifier<TripListState> {
  final TripRepository _repo;
  int _loadSeq = 0;

  TripListNotifier(this._repo) : super(const TripListState()) {
    loadTrips();
  }

  /// Reset session-scoped trip list on logout without triggering `/trips`.
  void resetForLogout() {
    _loadSeq++;
    state = const TripListState();
  }

  Future<void> loadTrips() async {
    final seq = ++_loadSeq;
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final list = await _repo.getMyTrips();
      if (!mounted || seq != _loadSeq) return;
      state = state.copyWith(trips: list, isLoading: false, clearError: true);
    } on DioException catch (e) {
      if (!mounted || seq != _loadSeq) return;
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isLoading: false,
        errorMessage: _mapError(e),
        isOfflineError: details.isOfflineOrTransient,
      );
    } catch (_) {
      if (!mounted || seq != _loadSeq) return;
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Không thể tải danh sách chuyến đi',
        isOfflineError: false,
      );
    }
  }

  Future<TripModel?> createTrip(CreateTripRequest request) async {
    try {
      final created = await _repo.createTrip(request);
      state = state.copyWith(
        trips: [created, ...state.trips],
        clearError: true,
      );
      return created;
    } on DioException catch (e) {
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        errorMessage: _mapError(e),
        isOfflineError: details.isOfflineOrTransient,
      );
      return null;
    }
  }

  Future<bool> deleteTrip(String id) async {
    try {
      await _repo.deleteTrip(id);
      state = state.copyWith(
        trips: state.trips.where((t) => t.id != id).toList(),
        clearError: true,
      );
      return true;
    } on DioException catch (e) {
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        errorMessage: _mapError(e),
        isOfflineError: details.isOfflineOrTransient,
      );
      return false;
    }
  }

  String _mapError(DioException e) {
    final details = ApiErrorDetails.fromDioException(e);
    if (details.isNetworkError) {
      return 'Không có kết nối mạng. Vui lòng kiểm tra kết nối và thử lại.';
    }
    if (details.statusCode == 401) {
      return 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.';
    }
    if (details.message != null) {
      return details.message!;
    }
    return 'Lỗi kết nối đến máy chủ. Vui lòng thử lại.';
  }
}

class TripDetailState {
  final TripModel? trip;
  final bool isLoading;
  final String? errorMessage;
  final bool isGeneratingPlan;
  final AiPlanPreviewModel? generatedPlan;
  final String? planErrorMessage;

  const TripDetailState({
    this.trip,
    this.isLoading = false,
    this.errorMessage,
    this.isGeneratingPlan = false,
    this.generatedPlan,
    this.planErrorMessage,
  });

  TripDetailState copyWith({
    TripModel? trip,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    bool? isGeneratingPlan,
    AiPlanPreviewModel? generatedPlan,
    bool clearPlan = false,
    String? planErrorMessage,
    bool clearPlanError = false,
  }) {
    return TripDetailState(
      trip: trip ?? this.trip,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      isGeneratingPlan: isGeneratingPlan ?? this.isGeneratingPlan,
      generatedPlan: clearPlan ? null : (generatedPlan ?? this.generatedPlan),
      planErrorMessage: clearPlanError
          ? null
          : (planErrorMessage ?? this.planErrorMessage),
    );
  }
}

class TripDetailNotifier extends StateNotifier<TripDetailState> {
  final TripRepository _repo;
  int _loadSeq = 0;

  TripDetailNotifier(this._repo) : super(const TripDetailState());

  /// Reset session-scoped trip detail on logout.
  void resetForLogout() {
    _loadSeq++;
    state = const TripDetailState();
  }

  Future<void> loadTrip(String id) async {
    final seq = ++_loadSeq;
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final detail = await _repo.getTripDetail(id);
      if (!mounted || seq != _loadSeq) return;
      state = state.copyWith(trip: detail, isLoading: false, clearError: true);
    } on DioException catch (e) {
      if (!mounted || seq != _loadSeq) return;
      state = state.copyWith(
        isLoading: false,
        errorMessage: _mapError(e),
      );
    } catch (_) {
      if (!mounted || seq != _loadSeq) return;
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Không thể tải chi tiết chuyến đi',
      );
    }
  }

  Future<bool> updateTrip(String id, UpdateTripRequest request) async {
    try {
      final updated = await _repo.updateTrip(id, request);
      state = state.copyWith(trip: updated);
      return true;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _mapError(e));
      return false;
    }
  }

  Future<bool> addItineraryItem(
    String tripId,
    AddItineraryItemRequest request,
  ) async {
    try {
      await _repo.addItineraryItem(tripId, request);
      // Reload trip detail to update all itineraries
      await loadTrip(tripId);
      return true;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _mapError(e));
      return false;
    }
  }

  Future<bool> deleteItineraryItem(String tripId, String itemId) async {
    try {
      await _repo.deleteItineraryItem(tripId, itemId);
      await loadTrip(tripId);
      return true;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _mapError(e));
      return false;
    }
  }

  Future<AiPlanPreviewModel?> generateAiPlan(
    String tripId, {
    String? prompt,
  }) async {
    state = state.copyWith(
      isGeneratingPlan: true,
      clearPlanError: true,
    );
    try {
      final plan = await _repo.generateAiPlan(tripId, prompt: prompt);
      state = state.copyWith(
        isGeneratingPlan: false,
        generatedPlan: plan,
        clearPlanError: true,
      );
      return plan;
    } on DioException catch (e) {
      state = state.copyWith(
        isGeneratingPlan: false,
        planErrorMessage: _mapError(e),
      );
      return null;
    } catch (_) {
      state = state.copyWith(
        isGeneratingPlan: false,
        planErrorMessage: 'Không thể tạo lịch trình từ AI. Vui lòng thử lại.',
      );
      return null;
    }
  }

  Future<bool> saveAiPlan(
    String tripId,
    AiPlanPreviewModel plan, {
    bool replaceExisting = true,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final updated = await _repo.bulkSaveItinerary(
        tripId,
        plan.toBulkSaveRequest(replaceExisting: replaceExisting),
      );
      state = state.copyWith(
        trip: updated,
        isLoading: false,
        clearPlan: true,
      );
      return true;
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: _mapError(e),
      );
      return false;
    } catch (_) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Lỗi khi lưu lịch trình vào chuyến đi',
      );
      return false;
    }
  }

  void clearGeneratedPlan() {
    state = state.copyWith(clearPlan: true, clearPlanError: true);
  }

  String _mapError(DioException e) {
    final details = ApiErrorDetails.fromDioException(e);
    if (details.isNetworkError) {
      return 'Không có kết nối mạng. Vui lòng kiểm tra kết nối và thử lại.';
    }
    if (details.statusCode == 403) {
      return 'Bạn không có quyền truy cập chuyến đi này.';
    }
    if (details.statusCode == 404) {
      return 'Chuyến đi không tồn tại hoặc đã bị xóa.';
    }
    if (details.message != null) {
      return details.message!;
    }
    return 'Lỗi kết nối. Vui lòng thử lại.';
  }
}

final tripRepositoryProvider = Provider<TripRepository>((ref) {
  final dio = ref.read(apiClientProvider);
  return TripRepository(dio);
});

final tripListProvider =
    StateNotifierProvider<TripListNotifier, TripListState>((ref) {
  final repo = ref.read(tripRepositoryProvider);
  return TripListNotifier(repo);
});

final tripDetailProvider =
    StateNotifierProvider<TripDetailNotifier, TripDetailState>((ref) {
  final repo = ref.read(tripRepositoryProvider);
  return TripDetailNotifier(repo);
});
