enum TripInviteStatus {
  pending,
  accepted,
  declined,
  revoked;

  static TripInviteStatus fromRaw(String? raw) {
    switch (raw?.toUpperCase()) {
      case 'ACCEPTED':
        return TripInviteStatus.accepted;
      case 'DECLINED':
        return TripInviteStatus.declined;
      case 'REVOKED':
        return TripInviteStatus.revoked;
      case 'PENDING':
      default:
        return TripInviteStatus.pending;
    }
  }

  String get labelVi {
    switch (this) {
      case TripInviteStatus.pending:
        return 'Chờ phản hồi';
      case TripInviteStatus.accepted:
        return 'Đã tham gia';
      case TripInviteStatus.declined:
        return 'Đã từ chối';
      case TripInviteStatus.revoked:
        return 'Đã thu hồi';
    }
  }
}

class NotificationTripInviteMeta {
  final String inviteId;
  final String tripId;
  final String tripTitle;
  final String? destinationName;
  final String inviterId;
  final String inviterDisplayName;
  final TripInviteStatus status;
  final DateTime? respondedAt;
  final DateTime? revokedAt;

  const NotificationTripInviteMeta({
    required this.inviteId,
    required this.tripId,
    required this.tripTitle,
    this.destinationName,
    required this.inviterId,
    required this.inviterDisplayName,
    required this.status,
    this.respondedAt,
    this.revokedAt,
  });

  factory NotificationTripInviteMeta.fromJson(Map<String, dynamic> json) {
    return NotificationTripInviteMeta(
      inviteId: json['inviteId'] as String? ?? '',
      tripId: json['tripId'] as String? ?? '',
      tripTitle: json['tripTitle'] as String? ?? 'Chuyến đi',
      destinationName: json['destinationName'] as String?,
      inviterId: json['inviterId'] as String? ?? '',
      inviterDisplayName:
          json['inviterDisplayName'] as String? ?? 'Người dùng GoMate',
      status: TripInviteStatus.fromRaw(json['status'] as String?),
      respondedAt: json['respondedAt'] != null
          ? DateTime.tryParse(json['respondedAt'].toString())
          : null,
      revokedAt: json['revokedAt'] != null
          ? DateTime.tryParse(json['revokedAt'].toString())
          : null,
    );
  }
}

class AppNotificationModel {
  final String id;
  final String userId;
  final String type;
  final String title;
  final String? body;
  final bool isRead;
  final DateTime createdAt;
  final Map<String, dynamic>? data;
  final NotificationTripInviteMeta? tripInvite;

  const AppNotificationModel({
    required this.id,
    required this.userId,
    required this.type,
    required this.title,
    this.body,
    required this.isRead,
    required this.createdAt,
    this.data,
    this.tripInvite,
  });

  bool get isTripInvite => type == 'TRIP_INVITE';

  String? get effectiveInviteId =>
      tripInvite?.inviteId ?? (data?['inviteId'] as String?);

  String? get effectiveTripId =>
      tripInvite?.tripId ?? (data?['tripId'] as String?);

  TripInviteStatus get effectiveInviteStatus =>
      tripInvite?.status ??
      TripInviteStatus.fromRaw(data?['status'] as String?);

  AppNotificationModel copyWith({
    bool? isRead,
    NotificationTripInviteMeta? tripInvite,
  }) {
    return AppNotificationModel(
      id: id,
      userId: userId,
      type: type,
      title: title,
      body: body,
      isRead: isRead ?? this.isRead,
      createdAt: createdAt,
      data: data,
      tripInvite: tripInvite ?? this.tripInvite,
    );
  }

  factory AppNotificationModel.fromJson(Map<String, dynamic> json) {
    final rawData = json['data'];
    final parsedData =
        rawData is Map<String, dynamic> ? rawData : null;
    final rawInvite = json['tripInvite'];
    return AppNotificationModel(
      id: json['id'] as String? ?? '',
      userId: json['userId'] as String? ?? '',
      type: json['type'] as String? ?? 'SYSTEM',
      title: json['title'] as String? ?? '',
      body: json['body'] as String?,
      isRead: json['isRead'] as bool? ?? false,
      createdAt: json['createdAt'] != null
          ? (DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now())
          : DateTime.now(),
      data: parsedData,
      tripInvite: rawInvite is Map<String, dynamic>
          ? NotificationTripInviteMeta.fromJson(rawInvite)
          : null,
    );
  }
}

class NotificationsListResult {
  final List<AppNotificationModel> items;
  final int unreadCount;

  const NotificationsListResult({
    required this.items,
    required this.unreadCount,
  });

  factory NotificationsListResult.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? const [];
    return NotificationsListResult(
      items: rawItems
          .whereType<Map<String, dynamic>>()
          .map(AppNotificationModel.fromJson)
          .toList(),
      unreadCount: (json['unreadCount'] as num?)?.toInt() ?? 0,
    );
  }
}

class TripInviteDetailModel {
  final String id;
  final String tripId;
  final String tripTitle;
  final String? tripDescription;
  final String? destinationName;
  final DateTime? startDate;
  final DateTime? endDate;
  final TripInviteStatus status;
  final String? notificationId;
  final String inviterId;
  final String inviterDisplayName;
  final String inviteeId;
  final String inviteeDisplayName;
  final String? inviteeEmail;
  final DateTime createdAt;
  final DateTime? respondedAt;
  final DateTime? revokedAt;
  final bool idempotentDuplicate;

  const TripInviteDetailModel({
    required this.id,
    required this.tripId,
    required this.tripTitle,
    this.tripDescription,
    this.destinationName,
    this.startDate,
    this.endDate,
    required this.status,
    this.notificationId,
    required this.inviterId,
    required this.inviterDisplayName,
    required this.inviteeId,
    required this.inviteeDisplayName,
    this.inviteeEmail,
    required this.createdAt,
    this.respondedAt,
    this.revokedAt,
    this.idempotentDuplicate = false,
  });

  factory TripInviteDetailModel.fromJson(Map<String, dynamic> json) {
    final inviter = json['inviter'] as Map<String, dynamic>? ?? const {};
    final invitee = json['invitee'] as Map<String, dynamic>? ?? const {};
    return TripInviteDetailModel(
      id: json['id'] as String? ?? '',
      tripId: json['tripId'] as String? ?? '',
      tripTitle: json['tripTitle'] as String? ?? 'Chuyến đi',
      tripDescription: json['tripDescription'] as String?,
      destinationName: json['destinationName'] as String?,
      startDate: json['startDate'] != null
          ? DateTime.tryParse(json['startDate'].toString())
          : null,
      endDate: json['endDate'] != null
          ? DateTime.tryParse(json['endDate'].toString())
          : null,
      status: TripInviteStatus.fromRaw(json['status'] as String?),
      notificationId: json['notificationId'] as String?,
      inviterId: inviter['id'] as String? ?? '',
      inviterDisplayName:
          inviter['displayName'] as String? ?? 'Người dùng GoMate',
      inviteeId: invitee['id'] as String? ?? '',
      inviteeDisplayName:
          invitee['displayName'] as String? ?? 'Người nhận',
      inviteeEmail: invitee['email'] as String?,
      createdAt: json['createdAt'] != null
          ? (DateTime.tryParse(json['createdAt'].toString()) ?? DateTime.now())
          : DateTime.now(),
      respondedAt: json['respondedAt'] != null
          ? DateTime.tryParse(json['respondedAt'].toString())
          : null,
      revokedAt: json['revokedAt'] != null
          ? DateTime.tryParse(json['revokedAt'].toString())
          : null,
      idempotentDuplicate: json['idempotentDuplicate'] as bool? ?? false,
    );
  }
}
