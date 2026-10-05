import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/trip_models.dart';
import '../data/trip_repository.dart';
import '../../../core/network/api_client.dart';

class TripListState {
  final List<TripModel> trips;
  final bool isLoading;
  final String? errorMessage;

  const TripListState({
    this.trips = const [],
    this.isLoading = false,
    this.errorMessage,
  });

  bool get isEmpty => !isLoading && trips.isEmpty && errorMessage == null;

  TripListState copyWith({
    List<TripModel>? trips,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
  }) {
    return TripListState(
      trips: trips ?? this.trips,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class TripListNotifier extends StateNotifier<TripListState> {
  final TripRepository _repo;

  TripListNotifier(this._repo) : super(const TripListState()) {
    loadTrips();
  }

  Future<void> loadTrips() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final list = await _repo.getMyTrips();
      state = state.copyWith(trips: list, isLoading: false, clearError: true);
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: _mapError(e),
      );
    } catch (_) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Khong the tai danh sach chuyen di',
      );
    }
  }

  Future<TripModel?> createTrip(CreateTripRequest request) async {
    try {
      final created = await _repo.createTrip(request);
      state = state.copyWith(
        trips: [created, ...state.trips],
      );
      return created;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _mapError(e));
      return null;
    }
  }

  Future<bool> deleteTrip(String id) async {
    try {
      await _repo.deleteTrip(id);
      state = state.copyWith(
        trips: state.trips.where((t) => t.id != id).toList(),
      );
      return true;
    } on DioException catch (e) {
      state = state.copyWith(errorMessage: _mapError(e));
      return false;
    }
  }

  String _mapError(DioException e) {
    if (e.response?.statusCode == 401) {
      return 'Phien dang nhap het han. Vui long dang nhap lai.';
    }
    final data = e.response?.data;
    if (data is Map && data['message'] is String) {
      return data['message'] as String;
    }
    return 'Loi ket noi den may chu. Vui long thu lai.';
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

  TripDetailNotifier(this._repo) : super(const TripDetailState());

  Future<void> loadTrip(String id) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final detail = await _repo.getTripDetail(id);
      state = state.copyWith(trip: detail, isLoading: false, clearError: true);
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: _mapError(e),
      );
    } catch (_) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Khong the tai chi tiet chuyen di',
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
        planErrorMessage: 'Khong the tao lich trinh tu AI. Vui long thu lai.',
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
        errorMessage: 'Loi khi luu lich trinh vao chuyen di',
      );
      return false;
    }
  }

  void clearGeneratedPlan() {
    state = state.copyWith(clearPlan: true, clearPlanError: true);
  }

  String _mapError(DioException e) {
    if (e.response?.statusCode == 403) {
      return 'Ban khong co quyen truy cap chuyen di nay.';
    }
    if (e.response?.statusCode == 404) {
      return 'Chuyen di khong ton tai hoac da bi xoa.';
    }
    final data = e.response?.data;
    if (data is Map && data['message'] is String) {
      return data['message'] as String;
    }
    return 'Loi ket noi. Vui long thu lai.';
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
