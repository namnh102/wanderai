/// Strongly typed Trip domain models & TripContext abstraction.

enum TravelStyle { backpacker, budget, comfort, luxury }

enum TripStatus { draft, planned, ongoing, completed, cancelled }

/// Formats VND integer with dot thousands separator (e.g. 80000 -> '80.000').
String formatDotVndAmount(int amount) {
  final raw = (amount < 0 ? 0 : amount).toString();
  final buf = StringBuffer();
  for (var i = 0; i < raw.length; i++) {
    if (i > 0 && (raw.length - i) % 3 == 0) {
      buf.write('.');
    }
    buf.write(raw[i]);
  }
  return buf.toString();
}

/// Builds C4-compliant budget summary text avoiding false remaining-surplus claims when prices are unknown.
String formatC4BudgetSummary({
  required int knownCostTotal,
  required int unknownCostCount,
  int? totalBudget,
  bool isOverBudget = false,
}) {
  final knownStr = '${formatDotVndAmount(knownCostTotal)}đ';
  if (unknownCostCount > 0) {
    if (isOverBudget && totalBudget != null && totalBudget > 0) {
      final over = (knownCostTotal - totalBudget).abs();
      return 'Đã biết $knownStr; còn khoản chưa xác minh (vượt ít nhất ${formatDotVndAmount(over)}đ)';
    }
    return 'Đã biết $knownStr; còn khoản chưa xác minh';
  }
  return 'Chi phí ước tính $knownStr';
}

class AiPlanRequestOptions {
  final String? additionalPrompt;
  final int? partySize;
  final String? partyDescription;
  final String? timeWindowStart;
  final String? timeWindowEnd;
  final int? budgetOverride;
  final List<String>? interestsOverride;

  const AiPlanRequestOptions({
    this.additionalPrompt,
    this.partySize,
    this.partyDescription,
    this.timeWindowStart,
    this.timeWindowEnd,
    this.budgetOverride,
    this.interestsOverride,
  });

  Map<String, dynamic> toJson() => {
        if (additionalPrompt != null && additionalPrompt!.trim().isNotEmpty)
          'additionalPrompt': additionalPrompt!.trim(),
        if (partySize != null && partySize! > 0) 'partySize': partySize,
        if (partyDescription != null && partyDescription!.trim().isNotEmpty)
          'partyDescription': partyDescription!.trim(),
        if (timeWindowStart != null && timeWindowStart!.trim().isNotEmpty)
          'timeWindowStart': timeWindowStart!.trim(),
        if (timeWindowEnd != null && timeWindowEnd!.trim().isNotEmpty)
          'timeWindowEnd': timeWindowEnd!.trim(),
        if (budgetOverride != null && budgetOverride! >= 0)
          'budgetOverride': budgetOverride,
        if (interestsOverride != null && interestsOverride!.isNotEmpty)
          'interestsOverride': interestsOverride,
      };
}

/// Formats start and end times so both endpoints are visible when present.
String? formatItineraryTimeRange(String? startTime, String? endTime) {
  final s = startTime?.trim();
  final e = endTime?.trim();
  final hasStart = s != null && s.isNotEmpty;
  final hasEnd = e != null && e.isNotEmpty;
  if (hasStart && hasEnd) {
    return '$s - $e';
  }
  if (hasStart) {
    return s;
  }
  if (hasEnd) {
    return 'Đến $e';
  }
  return null;
}

class ItineraryItemModel {
  final String id;
  final String itineraryId;
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

  const ItineraryItemModel({
    required this.id,
    required this.itineraryId,
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
  });

  factory ItineraryItemModel.fromJson(Map<String, dynamic> json) {
    final place = json['place'] as Map<String, dynamic>?;
    return ItineraryItemModel(
      id: json['id'] as String? ?? '',
      itineraryId: json['itineraryId'] as String? ?? '',
      placeId: (json['placeId'] as String?) ?? (place?['id'] as String?),
      placeName: place?['name'] as String?,
      placeAddress: place?['address'] as String?,
      orderIndex: json['orderIndex'] as int? ?? 1,
      startTime: json['startTime'] as String?,
      endTime: json['endTime'] as String?,
      activity: json['activity'] as String? ?? '',
      notes: json['notes'] as String?,
      estimatedCost: (json['estimatedCost'] as num?)?.toInt(),
      transportMode: json['transportMode'] as String?,
    );
  }

  ItineraryItemModel copyWith({
    int? orderIndex,
  }) {
    return ItineraryItemModel(
      id: id,
      itineraryId: itineraryId,
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
    );
  }
}

class ItineraryModel {
  final String id;
  final String tripId;
  final int dayNumber;
  final DateTime? date;
  final String? title;
  final List<ItineraryItemModel> items;

  const ItineraryModel({
    required this.id,
    required this.tripId,
    required this.dayNumber,
    this.date,
    this.title,
    this.items = const [],
  });

  factory ItineraryModel.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return ItineraryModel(
      id: json['id'] as String? ?? '',
      tripId: json['tripId'] as String? ?? '',
      dayNumber: json['dayNumber'] as int? ?? 1,
      date: json['date'] != null
          ? DateTime.tryParse(json['date'] as String)
          : null,
      title: json['title'] as String?,
      items: rawItems
          .map((i) => ItineraryItemModel.fromJson(i as Map<String, dynamic>))
          .toList(),
    );
  }

  ItineraryModel copyWith({
    List<ItineraryItemModel>? items,
  }) {
    return ItineraryModel(
      id: id,
      tripId: tripId,
      dayNumber: dayNumber,
      date: date,
      title: title,
      items: items ?? this.items,
    );
  }
}

class TripModel {
  final String id;
  final String userId;
  final String title;
  final String? description;
  final String? destinationId;
  final String? destinationName;
  final DateTime? startDate;
  final DateTime? endDate;
  final int? totalBudget;
  final String currency;
  final String? travelStyle;
  final List<String> interests;
  final String status;
  final List<ItineraryModel> itineraries;
  final int memberCount;

  const TripModel({
    required this.id,
    required this.userId,
    required this.title,
    this.description,
    this.destinationId,
    this.destinationName,
    this.startDate,
    this.endDate,
    this.totalBudget,
    this.currency = 'VND',
    this.travelStyle,
    this.interests = const [],
    this.status = 'DRAFT',
    this.itineraries = const [],
    this.memberCount = 1,
  });

  factory TripModel.fromJson(Map<String, dynamic> json) {
    final dest = json['destination'] as Map<String, dynamic>?;
    final rawItin = json['itineraries'] as List<dynamic>? ?? [];
    final counts = json['_count'] as Map<String, dynamic>?;

    return TripModel(
      id: json['id'] as String? ?? '',
      userId: json['userId'] as String? ?? '',
      title: json['title'] as String? ?? '',
      description: json['description'] as String?,
      destinationId: json['destinationId'] as String?,
      destinationName: dest?['name'] as String?,
      startDate: json['startDate'] != null
          ? DateTime.tryParse(json['startDate'] as String)
          : null,
      endDate: json['endDate'] != null
          ? DateTime.tryParse(json['endDate'] as String)
          : null,
      totalBudget: json['totalBudget'] as int?,
      currency: json['currency'] as String? ?? 'VND',
      travelStyle: json['travelStyle'] as String?,
      interests: (json['interests'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
      status: json['status'] as String? ?? 'DRAFT',
      itineraries: rawItin
          .map((i) => ItineraryModel.fromJson(i as Map<String, dynamic>))
          .toList(),
      memberCount: counts?['members'] as int? ?? 1,
    );
  }

  /// Converts this Trip to the standardized TripContext representation
  /// consumed by AI Agent, Recommendation, Booking, Matching, and Safety.
  TripContext toTripContext() {
    return TripContext(
      tripId: id,
      destination: destinationName ?? destinationId ?? '',
      startDate: startDate,
      endDate: endDate,
      budget: totalBudget,
      currency: currency,
      travelStyle: travelStyle,
      interests: interests,
      itinerary: itineraries,
    );
  }
}

/// Central TripContext abstraction.
class TripContext {
  final String tripId;
  final String destination;
  final DateTime? startDate;
  final DateTime? endDate;
  final int? budget;
  final String currency;
  final String? travelStyle;
  final List<String> interests;
  final List<ItineraryModel> itinerary;

  const TripContext({
    required this.tripId,
    required this.destination,
    this.startDate,
    this.endDate,
    this.budget,
    this.currency = 'VND',
    this.travelStyle,
    this.interests = const [],
    this.itinerary = const [],
  });

  Map<String, dynamic> toJson() => {
        'trip_id': tripId,
        'destination': destination,
        'start_date': startDate?.toIso8601String(),
        'end_date': endDate?.toIso8601String(),
        'budget': budget,
        'currency': currency,
        'travel_style': travelStyle,
        'interests': interests,
        'itinerary_days_count': itinerary.length,
      };
}

class CreateTripRequest {
  final String title;
  final String? description;
  final String? destinationId;
  final String? startDate;
  final String? endDate;
  final int? totalBudget;
  final String? currency;
  final String? travelStyle;
  final List<String>? interests;

  const CreateTripRequest({
    required this.title,
    this.description,
    this.destinationId,
    this.startDate,
    this.endDate,
    this.totalBudget,
    this.currency,
    this.travelStyle,
    this.interests,
  });

  Map<String, dynamic> toJson() => {
        'title': title,
        if (description != null && description!.isNotEmpty)
          'description': description,
        if (destinationId != null && destinationId!.isNotEmpty)
          'destinationId': destinationId,
        if (startDate != null && startDate!.isNotEmpty) 'startDate': startDate,
        if (endDate != null && endDate!.isNotEmpty) 'endDate': endDate,
        if (totalBudget != null) 'totalBudget': totalBudget,
        if (currency != null) 'currency': currency,
        if (travelStyle != null) 'travelStyle': travelStyle,
        if (interests != null) 'interests': interests,
      };
}

class UpdateTripRequest {
  final String? title;
  final String? description;
  final String? destinationId;
  final String? startDate;
  final String? endDate;
  final int? totalBudget;
  final String? currency;
  final String? travelStyle;
  final List<String>? interests;
  final String? status;

  const UpdateTripRequest({
    this.title,
    this.description,
    this.destinationId,
    this.startDate,
    this.endDate,
    this.totalBudget,
    this.currency,
    this.travelStyle,
    this.interests,
    this.status,
  });

  Map<String, dynamic> toJson() => {
        if (title != null) 'title': title,
        if (description != null) 'description': description,
        if (destinationId != null) 'destinationId': destinationId,
        if (startDate != null) 'startDate': startDate,
        if (endDate != null) 'endDate': endDate,
        if (totalBudget != null) 'totalBudget': totalBudget,
        if (currency != null) 'currency': currency,
        if (travelStyle != null) 'travelStyle': travelStyle,
        if (interests != null) 'interests': interests,
        if (status != null) 'status': status,
      };
}

class AddItineraryItemRequest {
  final int dayNumber;
  final String activity;
  final String? startTime;
  final String? endTime;
  final String? placeId;
  final String? notes;
  final int? estimatedCost;
  final String? transportMode;
  final String? clientRequestId;

  const AddItineraryItemRequest({
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

  Map<String, dynamic> toJson() => {
        'dayNumber': dayNumber,
        'activity': activity,
        if (startTime != null && startTime!.isNotEmpty) 'startTime': startTime,
        if (endTime != null && endTime!.isNotEmpty) 'endTime': endTime,
        if (placeId != null && placeId!.isNotEmpty) 'placeId': placeId,
        if (notes != null && notes!.isNotEmpty) 'notes': notes,
        if (estimatedCost != null) 'estimatedCost': estimatedCost,
        if (transportMode != null && transportMode!.isNotEmpty)
          'transportMode': transportMode,
        if (clientRequestId != null && clientRequestId!.isNotEmpty)
          'clientRequestId': clientRequestId,
      };
}

class ReorderItineraryItemEntry {
  final String itemId;
  final int orderIndex;

  const ReorderItineraryItemEntry({
    required this.itemId,
    required this.orderIndex,
  });

  Map<String, dynamic> toJson() => {
        'itemId': itemId,
        'orderIndex': orderIndex,
      };
}

class ReorderItineraryRequest {
  final int? dayNumber;
  final List<ReorderItineraryItemEntry> items;

  const ReorderItineraryRequest({
    this.dayNumber,
    required this.items,
  });

  Map<String, dynamic> toJson() => {
        if (dayNumber != null) 'dayNumber': dayNumber,
        'items': items.map((e) => e.toJson()).toList(),
      };
}

class ItineraryScheduleViolationModel {
  final String code;
  final String reasonCode;
  final int dayNumber;
  final int orderIndex;
  final int? conflictingOrderIndex;
  final String activity;
  final String? placeId;
  final String? placeName;
  final String? startTime;
  final String? endTime;
  final String? openingHours;
  final String message;

  const ItineraryScheduleViolationModel({
    required this.code,
    this.reasonCode = '',
    required this.dayNumber,
    required this.orderIndex,
    this.conflictingOrderIndex,
    required this.activity,
    this.placeId,
    this.placeName,
    this.startTime,
    this.endTime,
    this.openingHours,
    required this.message,
  });

  factory ItineraryScheduleViolationModel.fromJson(Map<String, dynamic> json) {
    return ItineraryScheduleViolationModel(
      code: json['code'] as String? ?? 'SCHEDULE_VIOLATION',
      reasonCode: (json['reasonCode'] as String?) ??
          (json['reason_code'] as String?) ??
          '',
      dayNumber:
          (json['dayNumber'] as int?) ?? (json['day_number'] as int?) ?? 1,
      orderIndex:
          (json['orderIndex'] as int?) ?? (json['order_index'] as int?) ?? 1,
      conflictingOrderIndex: (json['conflictingOrderIndex'] as int?) ??
          (json['conflicting_order_index'] as int?),
      activity: json['activity'] as String? ?? '',
      placeId: (json['placeId'] as String?) ?? (json['place_id'] as String?),
      placeName:
          (json['placeName'] as String?) ?? (json['place_name'] as String?),
      startTime:
          (json['startTime'] as String?) ?? (json['start_time'] as String?),
      endTime: (json['endTime'] as String?) ?? (json['end_time'] as String?),
      openingHours: (json['openingHours'] as String?) ??
          (json['opening_hours'] as String?),
      message: json['message'] as String? ?? 'Vi phạm ràng buộc lịch trình',
    );
  }
}

class AiPlanItemModel {
  final int orderIndex;
  final String? startTime;
  final String? endTime;
  final String activity;
  final String? placeId;
  final String? placeName;
  final String? notes;
  final int? estimatedCost;
  final String? costStatus;
  final String? transportMode;
  final String openingHoursStatus;
  final List<ItineraryScheduleViolationModel> violations;

  const AiPlanItemModel({
    required this.orderIndex,
    this.startTime,
    this.endTime,
    required this.activity,
    this.placeId,
    this.placeName,
    this.notes,
    this.estimatedCost,
    this.costStatus,
    this.transportMode,
    this.openingHoursStatus = 'UNKNOWN',
    this.violations = const [],
  });

  bool get isCostKnown => estimatedCost != null;

  String get effectiveCostStatus =>
      costStatus ?? (estimatedCost != null ? 'KNOWN' : 'UNKNOWN');

  factory AiPlanItemModel.fromJson(Map<String, dynamic> json) {
    final rawViolations = json['violations'] as List<dynamic>? ?? const [];
    final parsedCost = (json['estimatedCost'] as num?)?.toInt();
    return AiPlanItemModel(
      orderIndex: json['orderIndex'] as int? ?? 1,
      startTime: json['startTime'] as String?,
      endTime: json['endTime'] as String?,
      activity: json['activity'] as String? ?? '',
      placeId: json['placeId'] as String?,
      placeName: json['placeName'] as String?,
      notes: json['notes'] as String?,
      estimatedCost: parsedCost,
      costStatus: json['costStatus'] as String? ??
          (parsedCost != null ? 'KNOWN' : 'UNKNOWN'),
      transportMode: json['transportMode'] as String?,
      openingHoursStatus: json['openingHoursStatus'] as String? ?? 'UNKNOWN',
      violations: rawViolations
          .whereType<Map<String, dynamic>>()
          .map(ItineraryScheduleViolationModel.fromJson)
          .toList(),
    );
  }

  Map<String, dynamic> toBulkItemJson() {
    final hasResolvedPlaceId = placeId != null && placeId!.trim().isNotEmpty;
    final effectiveNotes = hasResolvedPlaceId
        ? notes
        : (placeName != null
            ? (notes != null ? '$notes ($placeName)' : placeName)
            : notes);
    return {
      'orderIndex': orderIndex,
      'activity': activity,
      if (startTime != null && startTime!.isNotEmpty) 'startTime': startTime,
      if (endTime != null && endTime!.isNotEmpty) 'endTime': endTime,
      if (hasResolvedPlaceId) 'placeId': placeId!.trim(),
      if (effectiveNotes != null && effectiveNotes.isNotEmpty)
        'notes': effectiveNotes,
      'estimatedCost': estimatedCost,
      if (transportMode != null && transportMode!.isNotEmpty)
        'transportMode': transportMode,
    };
  }
}

class AiPlanDayModel {
  final int dayNumber;
  final String? date;
  final String title;
  final int dayCost;
  final int unknownCostItemCount;
  final List<AiPlanItemModel> items;

  const AiPlanDayModel({
    required this.dayNumber,
    this.date,
    required this.title,
    this.dayCost = 0,
    this.unknownCostItemCount = 0,
    this.items = const [],
  });

  int get effectiveUnknownCostCount => unknownCostItemCount > 0
      ? unknownCostItemCount
      : items.where((i) => i.estimatedCost == null).length;

  factory AiPlanDayModel.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    final parsedItems = rawItems
        .map((i) => AiPlanItemModel.fromJson(i as Map<String, dynamic>))
        .toList();
    return AiPlanDayModel(
      dayNumber: json['dayNumber'] as int? ?? 1,
      date: json['date'] as String?,
      title: json['title'] as String? ?? 'Ngày ${json['dayNumber'] ?? 1}',
      dayCost: json['dayCost'] as int? ?? 0,
      unknownCostItemCount: json['unknownCostItemCount'] as int? ??
          parsedItems.where((i) => i.estimatedCost == null).length,
      items: parsedItems,
    );
  }

  Map<String, dynamic> toBulkDayJson() => {
        'dayNumber': dayNumber,
        if (date != null) 'date': date,
        'title': title,
        'items': items.map((i) => i.toBulkItemJson()).toList(),
      };
}

class BudgetAnalysisModel {
  final int? totalBudget;
  final int estimatedCost;
  final int? _knownCostTotal;
  final int unknownCostItemCount;
  final String? _costStatus;
  final bool? _hasSufficientBudgetBasis;
  final String currency;
  final bool isOverBudget;
  final int? variance;

  const BudgetAnalysisModel({
    this.totalBudget,
    this.estimatedCost = 0,
    int? knownCostTotal,
    this.unknownCostItemCount = 0,
    String? costStatus,
    bool? hasSufficientBudgetBasis,
    this.currency = 'VND',
    this.isOverBudget = false,
    this.variance,
  })  : _knownCostTotal = knownCostTotal,
        _costStatus = costStatus,
        _hasSufficientBudgetBasis = hasSufficientBudgetBasis;

  int get knownCostTotal => _knownCostTotal ?? estimatedCost;

  String get costStatus =>
      _costStatus ??
      (unknownCostItemCount > 0 ? 'PARTIAL_UNKNOWN' : 'COMPLETE');

  bool get hasSufficientBudgetBasis =>
      _hasSufficientBudgetBasis ??
      (totalBudget != null && totalBudget! > 0 && unknownCostItemCount == 0);

  factory BudgetAnalysisModel.fromJson(Map<String, dynamic> json) {
    final totalBudget = (json['totalBudget'] as num?)?.toInt();
    final estimated = (json['estimatedCost'] as num?)?.toInt() ?? 0;
    final known = (json['knownCostTotal'] as num?)?.toInt() ?? estimated;
    final unknownCount = (json['unknownCostItemCount'] as num?)?.toInt() ?? 0;
    return BudgetAnalysisModel(
      totalBudget: totalBudget,
      estimatedCost: estimated,
      knownCostTotal: known,
      unknownCostItemCount: unknownCount,
      costStatus: json['costStatus'] as String?,
      hasSufficientBudgetBasis: json['hasSufficientBudgetBasis'] as bool?,
      currency: json['currency'] as String? ?? 'VND',
      isOverBudget: json['isOverBudget'] as bool? ?? false,
      variance: (json['variance'] as num?)?.toInt(),
    );
  }
}

class AiPlanPreviewModel {
  final String tripId;
  final String destination;
  final int totalDays;
  final String overview;
  final String bestTimeToVisit;
  final List<String> generalTips;
  final BudgetAnalysisModel budgetAnalysis;
  final List<ItineraryScheduleViolationModel> scheduleViolations;
  final bool? _hasScheduleViolations;
  final bool? _canApply;
  final List<AiPlanDayModel> days;

  const AiPlanPreviewModel({
    required this.tripId,
    required this.destination,
    required this.totalDays,
    required this.overview,
    required this.bestTimeToVisit,
    this.generalTips = const [],
    required this.budgetAnalysis,
    this.scheduleViolations = const [],
    bool? hasScheduleViolations,
    bool? canApply,
    this.days = const [],
  })  : _hasScheduleViolations = hasScheduleViolations,
        _canApply = canApply;

  bool get hasScheduleViolations =>
      _hasScheduleViolations ??
      (scheduleViolations.isNotEmpty ||
          days.any((d) => d.items.any((i) => i.violations.isNotEmpty)));

  bool get canApply => _canApply ?? !hasScheduleViolations;

  factory AiPlanPreviewModel.fromJson(Map<String, dynamic> json) {
    final rawTips = json['generalTips'] as List<dynamic>? ?? [];
    final rawDays = json['days'] as List<dynamic>? ?? [];
    final rawViolations = json['scheduleViolations'] as List<dynamic>? ?? [];

    return AiPlanPreviewModel(
      tripId: json['tripId'] as String? ?? '',
      destination: json['destination'] as String? ?? '',
      totalDays: json['totalDays'] as int? ?? 1,
      overview: json['overview'] as String? ?? '',
      bestTimeToVisit: json['bestTimeToVisit'] as String? ?? '',
      generalTips: rawTips.map((t) => t.toString()).toList(),
      budgetAnalysis: json['budgetAnalysis'] != null
          ? BudgetAnalysisModel.fromJson(
              json['budgetAnalysis'] as Map<String, dynamic>)
          : const BudgetAnalysisModel(),
      scheduleViolations: rawViolations
          .whereType<Map<String, dynamic>>()
          .map(ItineraryScheduleViolationModel.fromJson)
          .toList(),
      hasScheduleViolations: json['hasScheduleViolations'] as bool?,
      canApply: json['canApply'] as bool?,
      days: rawDays
          .map((d) => AiPlanDayModel.fromJson(d as Map<String, dynamic>))
          .toList(),
    );
  }

  BulkSaveItineraryRequest toBulkSaveRequest({
    bool replaceExisting = true,
    String? clientRequestId,
  }) {
    return BulkSaveItineraryRequest(
      replaceExisting: replaceExisting,
      clientRequestId: clientRequestId,
      days: days.map((d) => d.toBulkDayJson()).toList(),
    );
  }
}

class BulkSaveItineraryRequest {
  final bool replaceExisting;
  final String? clientRequestId;
  final List<Map<String, dynamic>> days;

  const BulkSaveItineraryRequest({
    this.replaceExisting = true,
    this.clientRequestId,
    required this.days,
  });

  Map<String, dynamic> toJson() => {
        'replaceExisting': replaceExisting,
        if (clientRequestId != null && clientRequestId!.trim().isNotEmpty)
          'clientRequestId': clientRequestId!.trim(),
        'days': days,
      };
}
