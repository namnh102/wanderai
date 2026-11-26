import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_error.dart';
import '../data/group_models.dart';
import '../data/group_repository.dart';

class GroupListState {
  final List<GroupModel> groups;
  final bool isLoading;
  final bool isCreating;
  final String? errorMessage;
  final String? actionErrorMessage;
  final bool isOfflineError;
  final bool isForbidden;

  const GroupListState({
    this.groups = const [],
    this.isLoading = false,
    this.isCreating = false,
    this.errorMessage,
    this.actionErrorMessage,
    this.isOfflineError = false,
    this.isForbidden = false,
  });

  bool get isEmpty => !isLoading && groups.isEmpty && errorMessage == null;

  GroupListState copyWith({
    List<GroupModel>? groups,
    bool? isLoading,
    bool? isCreating,
    String? errorMessage,
    String? actionErrorMessage,
    bool? isOfflineError,
    bool? isForbidden,
    bool clearError = false,
    bool clearActionError = false,
  }) {
    return GroupListState(
      groups: groups ?? this.groups,
      isLoading: isLoading ?? this.isLoading,
      isCreating: isCreating ?? this.isCreating,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      actionErrorMessage: clearActionError
          ? null
          : (actionErrorMessage ?? this.actionErrorMessage),
      isOfflineError: isOfflineError ?? this.isOfflineError,
      isForbidden: isForbidden ?? this.isForbidden,
    );
  }
}

class GroupListNotifier extends StateNotifier<GroupListState> {
  final GroupRepository _repo;
  int _sessionSeq = 0;
  int _listLoadSeq = 0;
  int _createSeq = 0;
  final List<GroupModel> _createdDuringLoad = [];

  GroupListNotifier(this._repo) : super(const GroupListState());

  void resetForLogout() {
    _sessionSeq++;
    _listLoadSeq++;
    _createSeq++;
    _createdDuringLoad.clear();
    state = const GroupListState();
  }

  void clearActionError() {
    if (state.actionErrorMessage == null) return;
    state = state.copyWith(clearActionError: true);
  }

  Future<void> loadGroups() async {
    final session = _sessionSeq;
    final seq = ++_listLoadSeq;
    _createdDuringLoad.clear();
    state = state.copyWith(
      isLoading: true,
      clearError: true,
      clearActionError: true,
      isOfflineError: false,
      isForbidden: false,
    );
    try {
      final groups = await _repo.listGroups();
      if (!mounted || session != _sessionSeq || seq != _listLoadSeq) return;
      final merged = _createdDuringLoad.isEmpty
          ? groups
          : [
              ..._createdDuringLoad.where(
                (created) => !groups.any((g) => g.id == created.id),
              ),
              ...groups,
            ];
      _createdDuringLoad.clear();
      state = state.copyWith(groups: merged, isLoading: false);
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || seq != _listLoadSeq) return;
      _createdDuringLoad.clear();
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isLoading: false,
        isOfflineError: details.isNetworkError,
        isForbidden: details.statusCode == 403,
        errorMessage: _mapError(details, fallback: 'Không thể tải danh sách nhóm.'),
      );
    } catch (_) {
      if (!mounted || session != _sessionSeq || seq != _listLoadSeq) return;
      _createdDuringLoad.clear();
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Đã có lỗi xảy ra khi tải danh sách nhóm.',
      );
    }
  }

  Future<GroupModel?> createGroup(CreateGroupRequest request) async {
    final session = _sessionSeq;
    final createSeq = ++_createSeq;
    state = state.copyWith(isCreating: true, clearActionError: true);
    try {
      final created = await _repo.createGroup(request);
      if (!mounted || session != _sessionSeq || createSeq != _createSeq) {
        return null;
      }
      if (state.isLoading) {
        _createdDuringLoad.removeWhere((g) => g.id == created.id);
        _createdDuringLoad.insert(0, created);
      }
      final nextGroups = [
        created,
        ...state.groups.where((g) => g.id != created.id),
      ];
      state = state.copyWith(
        isCreating: false,
        groups: nextGroups,
      );
      return created;
    } on DioException catch (e) {
      if (!mounted || session != _sessionSeq || createSeq != _createSeq) {
        return null;
      }
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isCreating: false,
        actionErrorMessage:
            _mapError(details, fallback: 'Không thể tạo nhóm mới.'),
      );
      return null;
    } catch (_) {
      if (!mounted || session != _sessionSeq || createSeq != _createSeq) {
        return null;
      }
      state = state.copyWith(
        isCreating: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi tạo nhóm mới.',
      );
      return null;
    }
  }

  String _mapError(ApiErrorDetails details, {required String fallback}) {
    if (details.isNetworkError) {
      return 'Không có kết nối mạng. Vui lòng kiểm tra kết nối và thử lại.';
    }
    if (details.statusCode == 401) {
      return 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.';
    }
    if (details.statusCode == 403) {
      return details.message ?? 'Bạn không có quyền thực hiện thao tác này.';
    }
    if (details.statusCode == 409) {
      return details.message ?? 'Dữ liệu bị xung đột (nhóm đã tồn tại).';
    }
    return details.message ?? fallback;
  }
}

class GroupDetailState {
  final GroupModel? group;
  final bool isLoading;
  final bool isMutating;
  final String? errorMessage;
  final String? actionErrorMessage;
  final bool isForbidden;
  final bool isNotFound;
  final bool isOfflineError;

  const GroupDetailState({
    this.group,
    this.isLoading = false,
    this.isMutating = false,
    this.errorMessage,
    this.actionErrorMessage,
    this.isForbidden = false,
    this.isNotFound = false,
    this.isOfflineError = false,
  });

  GroupDetailState copyWith({
    GroupModel? group,
    bool? isLoading,
    bool? isMutating,
    String? errorMessage,
    String? actionErrorMessage,
    bool? isForbidden,
    bool? isNotFound,
    bool? isOfflineError,
    bool clearGroup = false,
    bool clearError = false,
    bool clearActionError = false,
  }) {
    return GroupDetailState(
      group: clearGroup ? null : (group ?? this.group),
      isLoading: isLoading ?? this.isLoading,
      isMutating: isMutating ?? this.isMutating,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      actionErrorMessage: clearActionError
          ? null
          : (actionErrorMessage ?? this.actionErrorMessage),
      isForbidden: isForbidden ?? this.isForbidden,
      isNotFound: isNotFound ?? this.isNotFound,
      isOfflineError: isOfflineError ?? this.isOfflineError,
    );
  }
}

class GroupDetailNotifier extends StateNotifier<GroupDetailState> {
  final GroupRepository _repo;
  int _loadSeq = 0;

  GroupDetailNotifier(this._repo) : super(const GroupDetailState());

  void resetForLogout() {
    _loadSeq++;
    state = const GroupDetailState();
  }

  void clearActionError() {
    state = state.copyWith(clearActionError: true);
  }

  Future<void> loadGroup(String id) async {
    final seq = ++_loadSeq;
    state = state.copyWith(
      isLoading: true,
      clearGroup: true,
      clearError: true,
      clearActionError: true,
      isForbidden: false,
      isNotFound: false,
      isOfflineError: false,
    );
    try {
      final group = await _repo.getGroup(id);
      if (!mounted || seq != _loadSeq) return;
      state = state.copyWith(group: group, isLoading: false);
    } on DioException catch (e) {
      if (!mounted || seq != _loadSeq) return;
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isLoading: false,
        isForbidden: details.statusCode == 403,
        isNotFound: details.statusCode == 404,
        isOfflineError: details.isNetworkError,
        errorMessage: _mapLoadError(details),
      );
    } catch (_) {
      if (!mounted || seq != _loadSeq) return;
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Không thể tải thông tin nhóm.',
      );
    }
  }

  Future<bool> updateGroup(String groupId, UpdateGroupRequest request) async {
    final seq = ++_loadSeq;
    state = state.copyWith(isMutating: true, clearActionError: true);
    try {
      final updated = await _repo.updateGroup(groupId, request);
      if (!mounted || seq != _loadSeq) return false;
      state = state.copyWith(group: updated, isMutating: false);
      return true;
    } on DioException catch (e) {
      if (!mounted || seq != _loadSeq) return false;
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isMutating: false,
        actionErrorMessage: _mapActionError(
          details,
          forbiddenFallback:
              'Bạn không có quyền chỉnh sửa nhóm này (chỉ Trưởng nhóm / admin).',
          fallback: 'Không thể cập nhật thông tin nhóm.',
        ),
      );
      return false;
    } catch (_) {
      if (!mounted || seq != _loadSeq) return false;
      state = state.copyWith(
        isMutating: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi cập nhật nhóm.',
      );
      return false;
    }
  }

  Future<bool> addMember(String groupId, String userId) async {
    final seq = ++_loadSeq;
    state = state.copyWith(isMutating: true, clearActionError: true);
    try {
      await _repo.addMember(groupId, AddGroupMemberRequest(userId: userId));
      final refreshed = await _repo.getGroup(groupId);
      if (!mounted || seq != _loadSeq) return false;
      state = state.copyWith(group: refreshed, isMutating: false);
      return true;
    } on DioException catch (e) {
      if (!mounted || seq != _loadSeq) return false;
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isMutating: false,
        actionErrorMessage: _mapActionError(
          details,
          forbiddenFallback:
              'Chỉ Trưởng nhóm (admin) mới có quyền thêm thành viên.',
          fallback: 'Không thể thêm thành viên vào nhóm.',
        ),
      );
      return false;
    } catch (_) {
      if (!mounted || seq != _loadSeq) return false;
      state = state.copyWith(
        isMutating: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi thêm thành viên.',
      );
      return false;
    }
  }

  Future<bool> removeMember(String groupId, String userId) async {
    final seq = ++_loadSeq;
    state = state.copyWith(isMutating: true, clearActionError: true);
    try {
      await _repo.removeMember(groupId, userId);
      final refreshed = await _repo.getGroup(groupId);
      if (!mounted || seq != _loadSeq) return false;
      state = state.copyWith(group: refreshed, isMutating: false);
      return true;
    } on DioException catch (e) {
      if (!mounted || seq != _loadSeq) return false;
      final details = ApiErrorDetails.fromDioException(e);
      state = state.copyWith(
        isMutating: false,
        actionErrorMessage: _mapActionError(
          details,
          forbiddenFallback:
              'Chỉ Trưởng nhóm (admin) mới có quyền xóa thành viên.',
          fallback: 'Không thể xóa thành viên khỏi nhóm.',
        ),
      );
      return false;
    } catch (_) {
      if (!mounted || seq != _loadSeq) return false;
      state = state.copyWith(
        isMutating: false,
        actionErrorMessage: 'Đã có lỗi xảy ra khi xóa thành viên.',
      );
      return false;
    }
  }

  String _mapLoadError(ApiErrorDetails details) {
    if (details.isNetworkError) {
      return 'Không có kết nối mạng. Vui lòng kiểm tra kết nối và thử lại.';
    }
    if (details.statusCode == 401) {
      return 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.';
    }
    if (details.statusCode == 403) {
      return details.message ?? 'Bạn không có quyền truy cập nhóm này.';
    }
    if (details.statusCode == 404) {
      return details.message ?? 'Nhóm không tồn tại hoặc đã bị xóa.';
    }
    return details.message ?? 'Không thể tải thông tin nhóm.';
  }

  String _mapActionError(
    ApiErrorDetails details, {
    required String forbiddenFallback,
    required String fallback,
  }) {
    if (details.isNetworkError) {
      return 'Không có kết nối mạng. Vui lòng kiểm tra kết nối và thử lại.';
    }
    if (details.statusCode == 401) {
      return 'Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.';
    }
    if (details.statusCode == 403) {
      return details.message ?? forbiddenFallback;
    }
    if (details.statusCode == 409) {
      return details.message ?? 'Thao tác bị từ chối do xung đột dữ liệu.';
    }
    if (details.statusCode == 404) {
      return details.message ?? 'Không tìm thấy nhóm hoặc người dùng.';
    }
    return details.message ?? fallback;
  }
}

final groupListProvider =
    StateNotifierProvider<GroupListNotifier, GroupListState>(
  (ref) => GroupListNotifier(ref.read(groupRepositoryProvider)),
);

final groupDetailProvider =
    StateNotifierProvider<GroupDetailNotifier, GroupDetailState>(
  (ref) => GroupDetailNotifier(ref.read(groupRepositoryProvider)),
);
