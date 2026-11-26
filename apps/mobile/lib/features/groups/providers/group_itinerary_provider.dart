import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_error.dart';
import '../../trips/data/trip_models.dart';
import '../data/group_itinerary_models.dart';
import '../data/group_repository.dart';

class GroupItineraryState {
  final GroupItineraryStateModel? itinerary;
  final bool isLoading;
  final bool isMutating;
  final String? errorMessage;
  final String? actionErrorMessage;
  final String? lastErrorCode;
  final bool isForbidden;
  final bool isTripAccessForbidden;
  final bool isOfflineError;

  const GroupItineraryState({
    this.itinerary,
    this.isLoading = false,
    this.isMutating = false,
    this.errorMessage,
    this.actionErrorMessage,
    this.lastErrorCode,
    this.isForbidden = false,
    this.isTripAccessForbidden = false,
    this.isOfflineError = false,
  });

  bool get isTripNotLinked =>
      itinerary != null && !itinerary!.tripLinked && errorMessage == null;

  GroupItineraryState copyWith({
    GroupItineraryStateModel? itinerary,
    bool? isLoading,
    bool? isMutating,
    String? errorMessage,
    String? actionErrorMessage,
    String? lastErrorCode,
    bool? isForbidden,
    bool? isTripAccessForbidden,
    bool? isOfflineError,
    bool clearItinerary = false,
    bool clearError = false,
    bool clearActionError = false,
    bool clearErrorCode = false,
  }) {
    return GroupItineraryState(
      itinerary: clearItinerary ? null : (itinerary ?? this.itinerary),
      isLoading: isLoading ?? this.isLoading,
      isMutating: isMutating ?? this.isMutating,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      actionErrorMessage: clearActionError
          ? null
          : (actionErrorMessage ?? this.actionErrorMessage),
      lastErrorCode:
          clearErrorCode ? null : (lastErrorCode ?? this.lastErrorCode),
      isForbidden: isForbidden ?? this.isForbidden,
      isTripAccessForbidden:
          isTripAccessForbidden ?? this.isTripAccessForbidden,
      isOfflineError: isOfflineError ?? this.isOfflineError,
    );
  }
}

class GroupItineraryNotifier extends StateNotifier<GroupItineraryState> {
  final GroupRepository _repo;
  int _sessionSeq = 0;
  int _loadSeq = 0;
  int _mutationSeq = 0;

  GroupItineraryNotifier(this._repo) : super(const GroupItineraryState());

  void resetForLogout() {
    _sessionSeq++;
    _loadSeq++;
    _mutationSeq++;
    state = const GroupItineraryState();
  }

  void clearActionError() {
    state = state.copyWith(clearActionError: true, clearErrorCode: true);
  }

  Future<void> loadItinerary(String groupId) async {
    final session = _sessionSeq;
    final seq = ++_loadSeq;
    state = state.copyWith(
      isLoading: true,
      clearError: true,
      clearActionError: true,
      clearErrorCode: true,
      isForbidden: false,
      isTripAccessForbidden: false,
      isOfflineError: false,
    );
    try {
      final res = await _repo.getGroupItinerary(groupId);
      if (!mounted || session != _sessionSeq || seq != _loadSeq) return;
      state = state.copyWith(itinerary: res, isLoading: false);
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || seq != _loadSeq) return;
      final details = ApiErrorDetails.fromDioException(e);
      final isTripForbidden =
          details.statusCode == 403 &&
          details.errorCode == 'TRIP_ACCESS_FORBIDDEN';
      state = state.copyWith(
        isLoading: false,
        clearItinerary: details.statusCode == 403 || details.statusCode == 404,
        lastErrorCode: details.errorCode,
        isForbidden: details.statusCode == 403,
        isTripAccessForbidden: isTripForbidden,
        isOfflineError: details.isOfflineOrTransient,
        errorMessage: _mapError(
          details,
          fallback: 'Không thể tải lịch trình nhóm.',
        ),
      );
    } catch (_) {
      if (!mounted || session != _sessionSeq || seq != _loadSeq) return;
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Đã có lỗi xảy ra khi tải lịch trình nhóm.',
      );
    }
  }

  Future<bool> proposeItem(
    String groupId,
    ProposeGroupItineraryItemRequest request,
  ) async {
    final session = _sessionSeq;
    final mutSeq = ++_mutationSeq;
    state = state.copyWith(
      isMutating: true,
      clearActionError: true,
      clearErrorCode: true,
    );
    try {
      await _repo.proposeItineraryItem(groupId, request);
      final refreshed = await _repo.getGroupItinerary(groupId);
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(itinerary: refreshed, isMutating: false);
      return true;
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isMutating: false,
        lastErrorCode: details.errorCode,
        actionErrorMessage: _mapError(
          details,
          fallback: 'Không thể đề xuất hoạt động mới.',
        ),
      );
      return false;
    } catch (_) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(
        isMutating: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi đề xuất hoạt động.',
      );
      return false;
    }
  }

  Future<bool> deleteItem(String groupId, String itemId) async {
    final session = _sessionSeq;
    final mutSeq = ++_mutationSeq;
    state = state.copyWith(
      isMutating: true,
      clearActionError: true,
      clearErrorCode: true,
    );
    try {
      await _repo.deleteItineraryItem(groupId, itemId);
      final refreshed = await _repo.getGroupItinerary(groupId);
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(itinerary: refreshed, isMutating: false);
      return true;
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isMutating: false,
        lastErrorCode: details.errorCode,
        actionErrorMessage: _mapError(
          details,
          fallback: 'Không thể xóa hoạt động khỏi lịch trình.',
        ),
      );
      return false;
    } catch (_) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(
        isMutating: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi xóa hoạt động.',
      );
      return false;
    }
  }

  Future<bool> reorderItems(
    String groupId,
    ReorderItineraryRequest request,
  ) async {
    final session = _sessionSeq;
    final mutSeq = ++_mutationSeq;
    state = state.copyWith(
      isMutating: true,
      clearActionError: true,
      clearErrorCode: true,
    );
    try {
      final updated = await _repo.reorderGroupItinerary(groupId, request);
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(itinerary: updated, isMutating: false);
      return true;
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isMutating: false,
        lastErrorCode: details.errorCode,
        actionErrorMessage: _mapError(
          details,
          fallback: 'Không thể đổi thứ tự lịch trình.',
        ),
      );
      return false;
    } catch (_) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(
        isMutating: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi đổi thứ tự lịch trình.',
      );
      return false;
    }
  }

  Future<bool> toggleOrSetVote(
    String groupId,
    GroupItineraryItemModel item,
    bool targetVote,
  ) async {
    final session = _sessionSeq;
    final mutSeq = ++_mutationSeq;
    state = state.copyWith(
      isMutating: true,
      clearActionError: true,
      clearErrorCode: true,
    );
    try {
      final GroupVoteResultModel result;
      if (item.myVote == targetVote) {
        result = await _repo.withdrawItineraryVote(groupId, item.id);
      } else {
        result = await _repo.voteItineraryItem(
          groupId,
          item.id,
          vote: targetVote,
        );
      }
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      final current = state.itinerary;
      if (current != null) {
        final nextDays = current.days.map((day) {
          return day.copyWith(
            items: day.items.map((it) {
              if (it.id != result.itemId) return it;
              return it.copyWith(
                upvotes: result.upvotes,
                downvotes: result.downvotes,
                score: result.score,
                myVote: result.myVote,
                clearMyVote: result.myVote == null,
              );
            }).toList(),
          );
        }).toList();
        state = state.copyWith(
          itinerary: current.copyWith(days: nextDays),
          isMutating: false,
        );
      } else {
        state = state.copyWith(isMutating: false);
      }
      return true;
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isMutating: false,
        lastErrorCode: details.errorCode,
        actionErrorMessage: _mapError(
          details,
          fallback: 'Không thể cập nhật phiếu bầu.',
        ),
      );
      return false;
    } catch (_) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(
        isMutating: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi bình chọn.',
      );
      return false;
    }
  }

  String _mapError(ApiErrorDetails details, {required String fallback}) {
    if (details.isOfflineOrTransient) {
      return 'Kết nối mạng gián đoạn. Vui lòng thử lại.';
    }
    if (details.statusCode == 401) {
      return 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.';
    }
    if (details.errorCode == 'TRIP_ACCESS_FORBIDDEN') {
      return details.message ??
          'Bạn thuộc nhóm đồng hành nhưng chưa được chủ chuyến cấp quyền thành viên chuyến đi.';
    }
    if (details.errorCode == 'GROUP_TRIP_NOT_LINKED') {
      return details.message ??
          'Nhóm chưa gắn chuyến đi hợp lệ để lập và bình chọn lịch trình.';
    }
    return details.message ?? fallback;
  }
}

final groupItineraryProvider =
    StateNotifierProvider<GroupItineraryNotifier, GroupItineraryState>(
  (ref) => GroupItineraryNotifier(ref.read(groupRepositoryProvider)),
);
