/// Strongly typed Trip domain models & TripContext abstraction.

enum TravelStyle { backpacker, budget, comfort, luxury }

enum TripStatus { draft, planned, ongoing, completed, cancelled }

class ItineraryItemModel {
  final String id;
  final String itineraryId;
  final String? placeId;
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
    required this.orderIndex,
    this.startTime,
    this.endTime,
    required this.activity,
    this.notes,
    this.estimatedCost,
    this.transportMode,
  });

  factory ItineraryItemModel.fromJson(Map<String, dynamic> json) {
    return ItineraryItemModel(
      id: json['id'] as String? ?? '',
      itineraryId: json['itineraryId'] as String? ?? '',
      placeId: json['placeId'] as String?,
      orderIndex: json['orderIndex'] as int? ?? 1,
      startTime: json['startTime'] as String?,
      endTime: json['endTime'] as String?,
      activity: json['activity'] as String? ?? '',
      notes: json['notes'] as String?,
      estimatedCost: json['estimatedCost'] as int?,
      transportMode: json['transportMode'] as String?,
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
      date: json['date'] != null ? DateTime.tryParse(json['date'] as String) : null,
      title: json['title'] as String?,
      items: rawItems
          .map((i) => ItineraryItemModel.fromJson(i as Map<String, dynamic>))
          .toList(),
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
/// Designed for future consumption by:
/// - AI Travel Agent
/// - Recommendation Engine
/// - Booking Flow
/// - Companion Matching
/// - Safety Check-ins
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

  const AddItineraryItemRequest({
    required this.dayNumber,
    required this.activity,
    this.startTime,
    this.endTime,
    this.placeId,
    this.notes,
    this.estimatedCost,
    this.transportMode,
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
      };
}
