import 'group_models.dart';

class GroupItineraryItemModel {
  final String id;
  final String itineraryId;
  final int dayNumber;
  final String? placeId;
  final String? placeName;
  final String? placeAddress;
  final int orderIndex;
  final String? startTime;
  final String? endTime;
  final String activity;
  final String? notes;
  final int? estimatedCost;
  final String? transportMode;
  final String? createdByUserId;
  final GroupMemberUserModel? createdBy;
  final int upvotes;
  final int downvotes;
  final int score;
  final bool? myVote;
  final bool canDelete;

  const GroupItineraryItemModel({
    required this.id,
    required this.itineraryId,
    required this.dayNumber,
    this.placeId,
    this.placeName,
    this.placeAddress,
    required this.orderIndex,
    this.startTime,
    this.endTime,
    required this.activity,
    this.notes,
    this.estimatedCost,
    this.transportMode,
    this.createdByUserId,
    this.createdBy,
    this.upvotes = 0,
    this.downvotes = 0,
    this.score = 0,
    this.myVote,
    this.canDelete = false,
  });

  GroupItineraryItemModel copyWith({
    int? orderIndex,
    int? upvotes,
    int? downvotes,
    int? score,
    bool? myVote,
    bool clearMyVote = false,
  }) {
    return GroupItineraryItemModel(
      id: id,
      itineraryId: itineraryId,
      dayNumber: dayNumber,
      placeId: placeId,
      placeName: placeName,
      placeAddress: placeAddress,
      orderIndex: orderIndex ?? this.orderIndex,
      startTime: startTime,
      endTime: endTime,
      activity: activity,
      notes: notes,
      estimatedCost: estimatedCost,
      transportMode: transportMode,
      createdByUserId: createdByUserId,
      createdBy: createdBy,
      upvotes: upvotes ?? this.upvotes,
      downvotes: downvotes ?? this.downvotes,
      score: score ?? this.score,
      myVote: clearMyVote ? null : (myVote ?? this.myVote),
      canDelete: canDelete,
    );
  }

  factory GroupItineraryItemModel.fromJson(Map<String, dynamic> json) {
    final placeMap = json['place'] is Map
        ? Map<String, dynamic>.from(json['place'] as Map)
        : null;
    final creatorMap = json['createdBy'] is Map
        ? Map<String, dynamic>.from(json['createdBy'] as Map)
        : null;
    final up = (json['upvotes'] as num?)?.toInt() ?? 0;
    final down = (json['downvotes'] as num?)?.toInt() ?? 0;

    return GroupItineraryItemModel(
      id: (json['id'] as String?) ?? '',
      itineraryId: (json['itineraryId'] as String?) ?? '',
      dayNumber: (json['dayNumber'] as num?)?.toInt() ?? 1,
      placeId: json['placeId'] as String?,
      placeName: placeMap?['name'] as String?,
      placeAddress: placeMap?['address'] as String?,
      orderIndex: (json['orderIndex'] as num?)?.toInt() ?? 1,
      startTime: json['startTime'] as String?,
      endTime: json['endTime'] as String?,
      activity: (json['activity'] as String?) ?? '',
      notes: json['notes'] as String?,
      estimatedCost: (json['estimatedCost'] as num?)?.toInt(),
      transportMode: json['transportMode'] as String?,
      createdByUserId: json['createdByUserId'] as String?,
      createdBy: creatorMap != null
          ? GroupMemberUserModel.fromJson(creatorMap)
          : null,
      upvotes: up,
      downvotes: down,
      score: (json['score'] as num?)?.toInt() ?? (up - down),
      myVote: json['myVote'] is bool ? (json['myVote'] as bool) : null,
      canDelete: json['canDelete'] == true,
    );
  }
}

class GroupItineraryDayModel {
  final String itineraryId;
  final int dayNumber;
  final DateTime? date;
  final String? title;
  final List<GroupItineraryItemModel> items;

  const GroupItineraryDayModel({
    required this.itineraryId,
    required this.dayNumber,
    this.date,
    this.title,
    this.items = const [],
  });

  GroupItineraryDayModel copyWith({List<GroupItineraryItemModel>? items}) {
    return GroupItineraryDayModel(
      itineraryId: itineraryId,
      dayNumber: dayNumber,
      date: date,
      title: title,
      items: items ?? this.items,
    );
  }

  factory GroupItineraryDayModel.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'];
    final items = rawItems is List
        ? rawItems
            .whereType<Map>()
            .map(
              (e) => GroupItineraryItemModel.fromJson(
                Map<String, dynamic>.from(e),
              ),
            )
            .toList()
        : const <GroupItineraryItemModel>[];

    final rawDate = json['date'];
    return GroupItineraryDayModel(
      itineraryId: (json['itineraryId'] as String?) ?? '',
      dayNumber: (json['dayNumber'] as num?)?.toInt() ?? 1,
      date: rawDate is String ? DateTime.tryParse(rawDate) : null,
      title: json['title'] as String?,
      items: items,
    );
  }
}

class GroupItineraryStateModel {
  final String groupId;
  final bool tripLinked;
  final String? tripId;
  final String? tripTitle;
  final String? tripStatus;
  final bool canAttachTrip;
  final bool canReorder;
  final String? guidanceMessage;
  final List<GroupItineraryDayModel> days;

  const GroupItineraryStateModel({
    required this.groupId,
    required this.tripLinked,
    this.tripId,
    this.tripTitle,
    this.tripStatus,
    this.canAttachTrip = false,
    this.canReorder = false,
    this.guidanceMessage,
    this.days = const [],
  });

  GroupItineraryStateModel copyWith({List<GroupItineraryDayModel>? days}) {
    return GroupItineraryStateModel(
      groupId: groupId,
      tripLinked: tripLinked,
      tripId: tripId,
      tripTitle: tripTitle,
      tripStatus: tripStatus,
      canAttachTrip: canAttachTrip,
      canReorder: canReorder,
      guidanceMessage: guidanceMessage,
      days: days ?? this.days,
    );
  }

  factory GroupItineraryStateModel.fromJson(Map<String, dynamic> json) {
    final rawDays = json['days'];
    final days = rawDays is List
        ? rawDays
            .whereType<Map>()
            .map(
              (e) => GroupItineraryDayModel.fromJson(
                Map<String, dynamic>.from(e),
              ),
            )
            .toList()
        : const <GroupItineraryDayModel>[];

    return GroupItineraryStateModel(
      groupId: (json['groupId'] as String?) ?? '',
      tripLinked: json['tripLinked'] == true,
      tripId: json['tripId'] as String?,
      tripTitle: json['tripTitle'] as String?,
      tripStatus: json['tripStatus'] as String?,
      canAttachTrip: json['canAttachTrip'] == true,
      canReorder: json['canReorder'] == true,
      guidanceMessage: json['guidanceMessage'] as String?,
      days: days,
    );
  }
}

class GroupVoteResultModel {
  final String itemId;
  final int upvotes;
  final int downvotes;
  final int score;
  final bool? myVote;

  const GroupVoteResultModel({
    required this.itemId,
    required this.upvotes,
    required this.downvotes,
    required this.score,
    this.myVote,
  });

  factory GroupVoteResultModel.fromJson(Map<String, dynamic> json) {
    final up = (json['upvotes'] as num?)?.toInt() ?? 0;
    final down = (json['downvotes'] as num?)?.toInt() ?? 0;
    return GroupVoteResultModel(
      itemId: (json['itemId'] as String?) ?? '',
      upvotes: up,
      downvotes: down,
      score: (json['score'] as num?)?.toInt() ?? (up - down),
      myVote: json['myVote'] is bool ? (json['myVote'] as bool) : null,
    );
  }
}

class ProposeGroupItineraryItemRequest {
  final int dayNumber;
  final String activity;
  final String? startTime;
  final String? endTime;
  final String? placeId;
  final String? notes;
  final int? estimatedCost;
  final String? transportMode;
  final String? clientRequestId;

  const ProposeGroupItineraryItemRequest({
    required this.dayNumber,
    required this.activity,
    this.startTime,
    this.endTime,
    this.placeId,
    this.notes,
    this.estimatedCost,
    this.transportMode,
    this.clientRequestId,
  });

  Map<String, dynamic> toJson() {
    return {
      'dayNumber': dayNumber,
      'activity': activity.trim(),
      if (startTime != null && startTime!.trim().isNotEmpty)
        'startTime': startTime!.trim(),
      if (endTime != null && endTime!.trim().isNotEmpty)
        'endTime': endTime!.trim(),
      if (placeId != null && placeId!.trim().isNotEmpty)
        'placeId': placeId!.trim(),
      if (notes != null && notes!.trim().isNotEmpty) 'notes': notes!.trim(),
      if (estimatedCost != null) 'estimatedCost': estimatedCost,
      if (transportMode != null && transportMode!.trim().isNotEmpty)
        'transportMode': transportMode!.trim(),
      if (clientRequestId != null && clientRequestId!.trim().isNotEmpty)
        'clientRequestId': clientRequestId!.trim(),
    };
  }
}
