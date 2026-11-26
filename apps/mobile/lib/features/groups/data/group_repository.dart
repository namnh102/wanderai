import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../trips/data/trip_models.dart';
import 'group_expense_models.dart';
import 'group_itinerary_models.dart';
import 'group_models.dart';

class GroupRepository {
  final Dio _dio;

  GroupRepository(this._dio);

  dynamic _unwrap(dynamic raw) {
    if (raw is Map && raw.containsKey('data')) {
      return raw['data'];
    }
    return raw;
  }

  Future<List<GroupModel>> listGroups() async {
    final res = await _dio.get('/groups');
    final data = _unwrap(res.data);
    if (data is! List) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi danh sách nhóm không hợp lệ',
      );
    }
    return data
        .whereType<Map>()
        .map((item) => GroupModel.fromJson(Map<String, dynamic>.from(item)))
        .toList();
  }

  Future<GroupModel> getGroup(String id) async {
    final res = await _dio.get('/groups/$id');
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi chi tiết nhóm không hợp lệ',
      );
    }
    return GroupModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<GroupModel> createGroup(CreateGroupRequest request) async {
    final res = await _dio.post('/groups', data: request.toJson());
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi tạo nhóm không hợp lệ',
      );
    }
    return GroupModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<GroupModel> updateGroup(String id, UpdateGroupRequest request) async {
    final res = await _dio.patch('/groups/$id', data: request.toJson());
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi cập nhật nhóm không hợp lệ',
      );
    }
    return GroupModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<void> addMember(String groupId, AddGroupMemberRequest request) async {
    await _dio.post('/groups/$groupId/members', data: request.toJson());
  }

  Future<void> removeMember(String groupId, String userId) async {
    await _dio.delete('/groups/$groupId/members/$userId');
  }

  Future<GroupItineraryStateModel> getGroupItinerary(String groupId) async {
    final res = await _dio.get('/groups/$groupId/itinerary');
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi lịch trình nhóm không hợp lệ',
      );
    }
    return GroupItineraryStateModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<GroupItineraryItemModel> proposeItineraryItem(
    String groupId,
    ProposeGroupItineraryItemRequest request,
  ) async {
    final res = await _dio.post(
      '/groups/$groupId/itinerary/items',
      data: request.toJson(),
    );
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi đề xuất hoạt động không hợp lệ',
      );
    }
    return GroupItineraryItemModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<void> deleteItineraryItem(String groupId, String itemId) async {
    await _dio.delete('/groups/$groupId/itinerary/items/$itemId');
  }

  Future<GroupItineraryStateModel> reorderGroupItinerary(
    String groupId,
    ReorderItineraryRequest request,
  ) async {
    final res = await _dio.put(
      '/groups/$groupId/itinerary/reorder',
      data: request.toJson(),
    );
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi đổi thứ tự lịch trình nhóm không hợp lệ',
      );
    }
    return GroupItineraryStateModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<GroupVoteResultModel> voteItineraryItem(
    String groupId,
    String itemId, {
    required bool vote,
  }) async {
    final res = await _dio.put(
      '/groups/$groupId/itinerary/items/$itemId/vote',
      data: {'vote': vote},
    );
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi bỏ phiếu không hợp lệ',
      );
    }
    return GroupVoteResultModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<GroupVoteResultModel> withdrawItineraryVote(
    String groupId,
    String itemId,
  ) async {
    final res = await _dio.delete(
      '/groups/$groupId/itinerary/items/$itemId/vote',
    );
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi rút phiếu không hợp lệ',
      );
    }
    return GroupVoteResultModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<ExpenseListModel> listExpenses(String groupId) async {
    final res = await _dio.get('/groups/$groupId/expenses');
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi sổ chi phí nhóm không hợp lệ',
      );
    }
    return ExpenseListModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<ExpenseModel> createExpense(
    String groupId,
    CreateExpenseRequest request,
  ) async {
    final res = await _dio.post(
      '/groups/$groupId/expenses',
      data: request.toJson(),
    );
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi tạo khoản chi không hợp lệ',
      );
    }
    return ExpenseModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<void> deleteExpense(String groupId, String expenseId) async {
    await _dio.delete('/groups/$groupId/expenses/$expenseId');
  }

  Future<SettlementPlanModel> getSettlementPlan(String groupId) async {
    final res = await _dio.get('/groups/$groupId/settlement-plan');
    final data = _unwrap(res.data);
    if (data is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi kế hoạch đối soát không hợp lệ',
      );
    }
    return SettlementPlanModel.fromJson(Map<String, dynamic>.from(data));
  }

  Future<SettlementModel> createSettlement(
    String groupId,
    CreateSettlementRequest request,
  ) async {
    final res = await _dio.post(
      '/groups/$groupId/settlements',
      data: request.toJson(),
    );
    final data = _unwrap(res.data);
    if (data is! Map || data['settlement'] is! Map) {
      throw DioException(
        requestOptions: res.requestOptions,
        response: res,
        message: 'Phản hồi ghi nhận đối soát không hợp lệ',
      );
    }
    return SettlementModel.fromJson(
      Map<String, dynamic>.from(data['settlement'] as Map),
    );
  }
}

final groupRepositoryProvider = Provider<GroupRepository>(
  (ref) => GroupRepository(ref.read(apiClientProvider)),
);
