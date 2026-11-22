import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import 'buddy_models.dart';

class BuddyRepository {
  final Dio _dio;

  BuddyRepository(this._dio);

  Future<List<BuddyCandidateModel>> getCandidates({int limit = 20}) async {
    final res = await _dio.get('/matches/candidates', queryParameters: {'limit': limit});
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    final items = inner is Map ? (inner['items'] as List? ?? const []) : const [];
    return items
        .whereType<Map>()
        .map((m) => BuddyCandidateModel.fromJson(Map<String, dynamic>.from(m)))
        .toList();
  }

  Future<List<BuddyMatchRecord>> getMyMatches() async {
    final res = await _dio.get('/matches');
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    final items = inner is Map ? (inner['items'] as List? ?? const []) : const [];
    return items
        .whereType<Map>()
        .map((m) => BuddyMatchRecord.fromJson(Map<String, dynamic>.from(m)))
        .toList();
  }

  Future<BuddyMatchRecord> sendRequest(String receiverId) async {
    final res = await _dio.post('/matches/request', data: {'receiverId': receiverId});
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    return BuddyMatchRecord.fromJson(Map<String, dynamic>.from(inner as Map));
  }

  Future<BuddyMatchRecord> respond(String matchId, String action) async {
    final res = await _dio.patch('/matches/$matchId/respond', data: {'action': action});
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    return BuddyMatchRecord.fromJson(Map<String, dynamic>.from(inner as Map));
  }
}

final buddyRepositoryProvider = Provider<BuddyRepository>((ref) {
  return BuddyRepository(ref.read(apiClientProvider));
});
