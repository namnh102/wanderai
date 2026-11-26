import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_error.dart';
import '../data/group_expense_models.dart';
import '../data/group_repository.dart';

class GroupExpenseState {
  final ExpenseListModel? expenseList;
  final SettlementPlanModel? settlementPlan;
  final bool isLoading;
  final bool isSubmitting;
  final String? errorMessage;
  final String? actionErrorMessage;
  final String? lastErrorCode;
  final bool isForbidden;
  final bool isOfflineError;

  const GroupExpenseState({
    this.expenseList,
    this.settlementPlan,
    this.isLoading = false,
    this.isSubmitting = false,
    this.errorMessage,
    this.actionErrorMessage,
    this.lastErrorCode,
    this.isForbidden = false,
    this.isOfflineError = false,
  });

  GroupExpenseState copyWith({
    ExpenseListModel? expenseList,
    SettlementPlanModel? settlementPlan,
    bool? isLoading,
    bool? isSubmitting,
    String? errorMessage,
    String? actionErrorMessage,
    String? lastErrorCode,
    bool? isForbidden,
    bool? isOfflineError,
    bool clearError = false,
    bool clearActionError = false,
    bool clearErrorCode = false,
  }) {
    return GroupExpenseState(
      expenseList: expenseList ?? this.expenseList,
      settlementPlan: settlementPlan ?? this.settlementPlan,
      isLoading: isLoading ?? this.isLoading,
      isSubmitting: isSubmitting ?? this.isSubmitting,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      actionErrorMessage: clearActionError
          ? null
          : (actionErrorMessage ?? this.actionErrorMessage),
      lastErrorCode:
          clearErrorCode ? null : (lastErrorCode ?? this.lastErrorCode),
      isForbidden: isForbidden ?? this.isForbidden,
      isOfflineError: isOfflineError ?? this.isOfflineError,
    );
  }
}

class GroupExpenseNotifier extends StateNotifier<GroupExpenseState> {
  final GroupRepository _repo;
  int _sessionSeq = 0;
  int _loadSeq = 0;
  int _mutationSeq = 0;

  GroupExpenseNotifier(this._repo) : super(const GroupExpenseState());

  void resetForLogout() {
    _sessionSeq++;
    _loadSeq++;
    _mutationSeq++;
    state = const GroupExpenseState();
  }

  void clearActionError() {
    state = state.copyWith(clearActionError: true, clearErrorCode: true);
  }

  Future<void> loadLedger(String groupId) async {
    final session = _sessionSeq;
    final seq = ++_loadSeq;
    state = state.copyWith(
      isLoading: true,
      clearError: true,
      clearActionError: true,
      clearErrorCode: true,
      isForbidden: false,
      isOfflineError: false,
    );
    try {
      final results = await Future.wait([
        _repo.listExpenses(groupId),
        _repo.getSettlementPlan(groupId),
      ]);
      if (!mounted || session != _sessionSeq || seq != _loadSeq) return;
      state = state.copyWith(
        expenseList: results[0] as ExpenseListModel,
        settlementPlan: results[1] as SettlementPlanModel,
        isLoading: false,
      );
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || seq != _loadSeq) return;
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isLoading: false,
        lastErrorCode: details.errorCode,
        isForbidden: details.statusCode == 403,
        isOfflineError: details.isOfflineOrTransient,
        errorMessage: _mapError(
          details,
          fallback: 'Không thể tải sổ chi phí nhóm.',
        ),
      );
    } catch (_) {
      if (!mounted || session != _sessionSeq || seq != _loadSeq) return;
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Đã có lỗi xảy ra khi tải sổ chi phí.',
      );
    }
  }

  Future<bool> createExpense(
    String groupId,
    CreateExpenseRequest request,
  ) async {
    final session = _sessionSeq;
    final mutSeq = ++_mutationSeq;
    state = state.copyWith(
      isSubmitting: true,
      clearActionError: true,
      clearErrorCode: true,
    );
    try {
      await _repo.createExpense(groupId, request);
      final results = await Future.wait([
        _repo.listExpenses(groupId),
        _repo.getSettlementPlan(groupId),
      ]);
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(
        expenseList: results[0] as ExpenseListModel,
        settlementPlan: results[1] as SettlementPlanModel,
        isSubmitting: false,
      );
      return true;
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isSubmitting: false,
        lastErrorCode: details.errorCode,
        actionErrorMessage: _mapError(
          details,
          fallback: 'Không thể thêm khoản chi mới.',
        ),
      );
      return false;
    } catch (_) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(
        isSubmitting: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi thêm khoản chi.',
      );
      return false;
    }
  }

  Future<bool> deleteExpense(String groupId, String expenseId) async {
    final session = _sessionSeq;
    final mutSeq = ++_mutationSeq;
    state = state.copyWith(
      isSubmitting: true,
      clearActionError: true,
      clearErrorCode: true,
    );
    try {
      await _repo.deleteExpense(groupId, expenseId);
      final results = await Future.wait([
        _repo.listExpenses(groupId),
        _repo.getSettlementPlan(groupId),
      ]);
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(
        expenseList: results[0] as ExpenseListModel,
        settlementPlan: results[1] as SettlementPlanModel,
        isSubmitting: false,
      );
      return true;
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isSubmitting: false,
        lastErrorCode: details.errorCode,
        actionErrorMessage: _mapError(
          details,
          fallback: 'Không thể xóa khoản chi.',
        ),
      );
      return false;
    } catch (_) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(
        isSubmitting: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi xóa khoản chi.',
      );
      return false;
    }
  }

  Future<bool> confirmSettlement(
    String groupId,
    CreateSettlementRequest request,
  ) async {
    final session = _sessionSeq;
    final mutSeq = ++_mutationSeq;
    state = state.copyWith(
      isSubmitting: true,
      clearActionError: true,
      clearErrorCode: true,
    );
    try {
      await _repo.createSettlement(groupId, request);
      final results = await Future.wait([
        _repo.listExpenses(groupId),
        _repo.getSettlementPlan(groupId),
      ]);
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(
        expenseList: results[0] as ExpenseListModel,
        settlementPlan: results[1] as SettlementPlanModel,
        isSubmitting: false,
      );
      return true;
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isSubmitting: false,
        lastErrorCode: details.errorCode,
        actionErrorMessage: _mapError(
          details,
          fallback: 'Không thể ghi nhận đối soát hoàn trả.',
        ),
      );
      return false;
    } catch (_) {
      if (!mounted || session != _sessionSeq || mutSeq != _mutationSeq) {
        return false;
      }
      state = state.copyWith(
        isSubmitting: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi xác nhận đối soát.',
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
    return details.message ?? fallback;
  }
}

final groupExpenseProvider =
    StateNotifierProvider<GroupExpenseNotifier, GroupExpenseState>(
  (ref) => GroupExpenseNotifier(ref.read(groupRepositoryProvider)),
);
