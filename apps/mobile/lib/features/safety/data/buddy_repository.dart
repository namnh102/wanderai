import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import 'buddy_models.dart';

class BuddyRepository {
  final Dio _dio;

  BuddyRepository(this._dio);

  Future<bool> getDiscoveryConsent() async {
    final res = await _dio.get('/matches/discovery');
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    if (inner is Map && inner['isDiscoverable'] is bool) {
      return inner['isDiscoverable'] as bool;
    }
    return false;
  }

  Future<bool> updateDiscoveryConsent(bool isDiscoverable) async {
    final res = await _dio.patch(
      '/matches/discovery',
      data: {'isDiscoverable': isDiscoverable},
    );
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    if (inner is Map && inner['isDiscoverable'] is bool) {
      return inner['isDiscoverable'] as bool;
    }
    return isDiscoverable;
  }

  Future<BuddyCandidatesResponse> getCandidatesWithConsent({
    String? destinationId,
    int limit = 20,
  }) async {
    final res = await _dio.get(
      '/matches/candidates',
      queryParameters: {
        'limit': limit,
        if (destinationId != null && destinationId.isNotEmpty)
          'destinationId': destinationId,
      },
    );
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    final isDiscoverable = inner is Map && inner['isDiscoverable'] is bool
        ? inner['isDiscoverable'] as bool
        : true;
    final items =
        inner is Map ? (inner['items'] as List? ?? const []) : const [];
    return BuddyCandidatesResponse(
      isDiscoverable: isDiscoverable,
      items: items
          .whereType<Map>()
          .map(
            (m) => BuddyCandidateModel.fromJson(Map<String, dynamic>.from(m)),
          )
          .toList(),
    );
  }

  Future<List<BuddyCandidateModel>> getCandidates({
    String? destinationId,
    int limit = 20,
  }) async {
    final res = await getCandidatesWithConsent(
      destinationId: destinationId,
      limit: limit,
    );
    return res.items;
  }

  Future<BuddyMaskedProfileModel> getMaskedProfile(String peerId) async {
    final res = await _dio.get('/matches/peers/$peerId');
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    return BuddyMaskedProfileModel.fromJson(
      Map<String, dynamic>.from(inner as Map),
    );
  }

  Future<List<BuddyMatchRecord>> getMyMatches() async {
    final res = await _dio.get('/matches');
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    final items =
        inner is Map ? (inner['items'] as List? ?? const []) : const [];
    return items
        .whereType<Map>()
        .map((m) => BuddyMatchRecord.fromJson(Map<String, dynamic>.from(m)))
        .toList();
  }

  Future<BuddyMatchRecord> sendRequest(String receiverId) async {
    final res = await _dio.post(
      '/matches/request',
      data: {'receiverId': receiverId},
    );
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    return BuddyMatchRecord.fromJson(Map<String, dynamic>.from(inner as Map));
  }

  Future<BuddyMatchRecord> withdrawRequest(String matchId) async {
    final res = await _dio.patch('/matches/$matchId/withdraw');
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    return BuddyMatchRecord.fromJson(Map<String, dynamic>.from(inner as Map));
  }

  Future<BuddyMatchRecord> respond(String matchId, String action) async {
    final res = await _dio.patch(
      '/matches/$matchId/respond',
      data: {'action': action},
    );
    final raw = res.data;
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    return BuddyMatchRecord.fromJson(Map<String, dynamic>.from(inner as Map));
  }

  Future<void> blockUser(String blockedUserId) async {
    await _dio.post(
      '/matches/blocks',
      data: {'blockedUserId': blockedUserId},
    );
  }
}

final buddyRepositoryProvider = Provider<BuddyRepository>((ref) {
  return BuddyRepository(ref.read(apiClientProvider));
});
