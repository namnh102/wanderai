import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/profile_models.dart';
import '../data/profile_repository.dart';

enum ProfileEditStatus {
  initialLoading,
  loaded,
  dirty,
  saving,
  success,
  validationError,
  networkError,
}

class ProfileState {
  final ProfileEditStatus status;
  final UserProfile? user;
  final TravelPreferences? persistedPreferences;
  final TravelPreferences formPreferences;
  final String? errorMessage;
  final String? successMessage;

  const ProfileState({
    required this.status,
    this.user,
    this.persistedPreferences,
    required this.formPreferences,
    this.errorMessage,
    this.successMessage,
  });

  bool get isLoading => status == ProfileEditStatus.initialLoading;
  bool get isSaving => status == ProfileEditStatus.saving;
  bool get isDirty => status == ProfileEditStatus.dirty;

  ProfileState copyWith({
    ProfileEditStatus? status,
    UserProfile? user,
    TravelPreferences? persistedPreferences,
    TravelPreferences? formPreferences,
    String? errorMessage,
    String? successMessage,
    bool clearErrors = false,
  }) {
    return ProfileState(
      status: status ?? this.status,
      user: user ?? this.user,
      persistedPreferences: persistedPreferences ?? this.persistedPreferences,
      formPreferences: formPreferences ?? this.formPreferences,
      errorMessage: clearErrors ? null : (errorMessage ?? this.errorMessage),
      successMessage: clearErrors ? null : (successMessage ?? this.successMessage),
    );
  }
}

class ProfileNotifier extends StateNotifier<ProfileState> {
  final ProfileRepository _repo;

  ProfileNotifier(this._repo)
      : super(const ProfileState(
          status: ProfileEditStatus.initialLoading,
          formPreferences: TravelPreferences(),
        )) {
    loadProfile();
  }

  Future<void> loadProfile() async {
    state = state.copyWith(status: ProfileEditStatus.initialLoading, clearErrors: true);
    try {
      final user = await _repo.getProfile();
      final prefs = user.preferences ?? const TravelPreferences();
      state = state.copyWith(
        status: ProfileEditStatus.loaded,
        user: user,
        persistedPreferences: prefs,
        formPreferences: prefs,
      );
    } on DioException catch (e) {
      state = state.copyWith(
        status: ProfileEditStatus.networkError,
        errorMessage: _mapError(e),
      );
    } catch (e) {
      state = state.copyWith(
        status: ProfileEditStatus.networkError,
        errorMessage: 'Lỗi tải thông tin: $e',
      );
    }
  }

  void setTravelStyle(TravelStyle style) {
    if (state.formPreferences.travelStyle == style) return;
    state = state.copyWith(
      status: ProfileEditStatus.dirty,
      formPreferences: state.formPreferences.copyWith(travelStyle: style),
      clearErrors: true,
    );
  }

  void setBudget(int min, int max) {
    state = state.copyWith(
      status: ProfileEditStatus.dirty,
      formPreferences: state.formPreferences.copyWith(budgetMin: min, budgetMax: max),
      clearErrors: true,
    );
  }

  void setPreferredGroup(GroupSize group) {
    if (state.formPreferences.preferredGroup == group) return;
    state = state.copyWith(
      status: ProfileEditStatus.dirty,
      formPreferences: state.formPreferences.copyWith(preferredGroup: group),
      clearErrors: true,
    );
  }

  void toggleInterest(String interestKey) {
    final current = List<String>.from(state.formPreferences.interests);
    if (current.contains(interestKey)) {
      current.remove(interestKey);
    } else {
      current.add(interestKey);
    }
    state = state.copyWith(
      status: ProfileEditStatus.dirty,
      formPreferences: state.formPreferences.copyWith(interests: current),
      clearErrors: true,
    );
  }

  void toggleAvoidance(String avoidance) {
    final current = List<String>.from(state.formPreferences.avoidances);
    if (current.contains(avoidance)) {
      current.remove(avoidance);
    } else {
      current.add(avoidance);
    }
    state = state.copyWith(
      status: ProfileEditStatus.dirty,
      formPreferences: state.formPreferences.copyWith(avoidances: current),
      clearErrors: true,
    );
  }

  void toggleDietary(String dietary) {
    final current = List<String>.from(state.formPreferences.dietaryNeeds);
    if (current.contains(dietary)) {
      current.remove(dietary);
    } else {
      current.add(dietary);
    }
    state = state.copyWith(
      status: ProfileEditStatus.dirty,
      formPreferences: state.formPreferences.copyWith(dietaryNeeds: current),
      clearErrors: true,
    );
  }

  Future<bool> savePreferences() async {
    // 1. Prevent duplicate submission
    if (state.status == ProfileEditStatus.saving) {
      return false;
    }

    // 2. Client-side validation
    final min = state.formPreferences.budgetMin;
    final max = state.formPreferences.budgetMax;

    if (min < 0) {
      state = state.copyWith(
        status: ProfileEditStatus.validationError,
        errorMessage: 'Ngân sách tối thiểu không được nhỏ hơn 0',
      );
      return false;
    }
    if (max < 0) {
      state = state.copyWith(
        status: ProfileEditStatus.validationError,
        errorMessage: 'Ngân sách tối đa không được nhỏ hơn 0',
      );
      return false;
    }
    if (min > max) {
      state = state.copyWith(
        status: ProfileEditStatus.validationError,
        errorMessage: 'Ngân sách tối thiểu không được lớn hơn ngân sách tối đa',
      );
      return false;
    }

    // 3. Mark saving
    state = state.copyWith(status: ProfileEditStatus.saving, clearErrors: true);

    try {
      final updated = await _repo.updatePreferences(state.formPreferences);
      state = state.copyWith(
        status: ProfileEditStatus.success,
        persistedPreferences: updated,
        formPreferences: updated,
        successMessage: 'Lưu sở thích du lịch thành công!',
      );
      return true;
    } on DioException catch (e) {
      state = state.copyWith(
        status: ProfileEditStatus.networkError,
        errorMessage: _mapError(e),
      );
      return false;
    } catch (e) {
      state = state.copyWith(
        status: ProfileEditStatus.networkError,
        errorMessage: 'Lỗi không xác định: $e',
      );
      return false;
    }
  }

  String _mapError(DioException e) {
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return 'Không thể kết nối máy chủ. Vui lòng thử lại.';
    }
    if (e.type == DioExceptionType.connectionError) {
      return 'Không có kết nối mạng.';
    }
    final data = e.response?.data;
    if (data is Map && data['message'] != null) {
      return data['message'].toString();
    }
    return 'Lỗi máy chủ (${e.response?.statusCode ?? 'Unknown'}). Vui lòng thử lại.';
  }
}

final profileProvider = StateNotifierProvider<ProfileNotifier, ProfileState>((ref) {
  final repo = ref.read(profileRepositoryProvider);
  return ProfileNotifier(repo);
});
