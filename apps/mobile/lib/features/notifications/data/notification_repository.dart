import 'package:dio/dio.dart';
import 'notification_models.dart';

class NotificationRepository {
  final Dio _dio;

  NotificationRepository(this._dio);

  /// GET /notifications — list notifications + authoritative unreadCount
  Future<NotificationsListResult> getNotifications({int limit = 50}) async {
    final response = await _dio.get(
      '/notifications',
      queryParameters: {'limit': limit},
    );
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return NotificationsListResult.fromJson(
        data['data'] as Map<String, dynamic>,
      );
    }
    return const NotificationsListResult(items: [], unreadCount: 0);
  }

  /// GET /notifications/unread-count
  Future<int> getUnreadCount() async {
    final response = await _dio.get('/notifications/unread-count');
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      final inner = data['data'] as Map<String, dynamic>;
      return (inner['unreadCount'] as num?)?.toInt() ?? 0;
    }
    return 0;
  }

  /// PATCH /notifications/:id/read
  Future<int> markRead(String notificationId) async {
    final response = await _dio.patch('/notifications/$notificationId/read');
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      final inner = data['data'] as Map<String, dynamic>;
      return (inner['unreadCount'] as num?)?.toInt() ?? 0;
    }
    return 0;
  }

  /// POST /notifications/read-all
  Future<void> markAllRead() async {
    await _dio.post('/notifications/read-all');
  }

  /// POST /trips/:tripId/invites — send trip invite by email
  Future<TripInviteDetailModel> sendTripInvite(
    String tripId,
    String email,
  ) async {
    final response = await _dio.post(
      '/trips/$tripId/invites',
      data: {'email': email.trim()},
    );
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return TripInviteDetailModel.fromJson(
        data['data'] as Map<String, dynamic>,
      );
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Invalid trip invite response format',
    );
  }

  /// GET /trips/:tripId/invites — owner lists outgoing invites for a trip
  Future<List<TripInviteDetailModel>> listTripInvites(String tripId) async {
    final response = await _dio.get('/trips/$tripId/invites');
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is List) {
      return (data['data'] as List<dynamic>)
          .whereType<Map<String, dynamic>>()
          .map(TripInviteDetailModel.fromJson)
          .toList();
    }
    return const [];
  }

  /// GET /trips/invites/:inviteId — invitee/inviter views invite detail
  Future<TripInviteDetailModel> getTripInviteDetail(String inviteId) async {
    final response = await _dio.get('/trips/invites/$inviteId');
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return TripInviteDetailModel.fromJson(
        data['data'] as Map<String, dynamic>,
      );
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Invalid trip invite detail response format',
    );
  }

  /// POST /trips/invites/:inviteId/accept
  Future<({TripInviteDetailModel invite, String tripId})> acceptTripInvite(
    String inviteId,
  ) async {
    final response = await _dio.post('/trips/invites/$inviteId/accept');
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      final inner = data['data'] as Map<String, dynamic>;
      final rawInvite = inner['invite'] as Map<String, dynamic>? ?? inner;
      final invite = TripInviteDetailModel.fromJson(rawInvite);
      final tripId = inner['tripId'] as String? ?? invite.tripId;
      return (invite: invite, tripId: tripId);
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Invalid accept trip invite response format',
    );
  }

  /// POST /trips/invites/:inviteId/decline
  Future<TripInviteDetailModel> declineTripInvite(String inviteId) async {
    final response = await _dio.post('/trips/invites/$inviteId/decline');
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return TripInviteDetailModel.fromJson(
        data['data'] as Map<String, dynamic>,
      );
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Invalid decline trip invite response format',
    );
  }

  /// POST /trips/:tripId/invites/:inviteId/revoke
  Future<TripInviteDetailModel> revokeTripInvite(
    String tripId,
    String inviteId,
  ) async {
    final response = await _dio.post('/trips/$tripId/invites/$inviteId/revoke');
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return TripInviteDetailModel.fromJson(
        data['data'] as Map<String, dynamic>,
      );
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Invalid revoke trip invite response format',
    );
  }
}
