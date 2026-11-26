import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
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
}

final groupRepositoryProvider = Provider<GroupRepository>(
  (ref) => GroupRepository(ref.read(apiClientProvider)),
);
