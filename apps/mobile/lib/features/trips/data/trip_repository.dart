import 'package:dio/dio.dart';
import 'trip_models.dart';

class TripRepository {
  final Dio _dio;

  TripRepository(this._dio);

  /// GET /trips — List my trips
  Future<List<TripModel>> getMyTrips() async {
    final response = await _dio.get('/trips');
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is List) {
      final list = data['data'] as List<dynamic>;
      return list
          .map((item) => TripModel.fromJson(item as Map<String, dynamic>))
          .toList();
    }
    return [];
  }

  /// GET /trips/:id — Trip detail with itineraries and members
  Future<TripModel> getTripDetail(String id) async {
    final response = await _dio.get('/trips/$id');
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return TripModel.fromJson(data['data'] as Map<String, dynamic>);
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Invalid trip detail response format',
    );
  }

  /// POST /trips — Create new trip
  Future<TripModel> createTrip(CreateTripRequest request) async {
    final response = await _dio.post('/trips', data: request.toJson());
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return TripModel.fromJson(data['data'] as Map<String, dynamic>);
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Failed to parse created trip',
    );
  }

  /// PUT /trips/:id — Update existing trip
  Future<TripModel> updateTrip(String id, UpdateTripRequest request) async {
    final response = await _dio.put('/trips/$id', data: request.toJson());
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return TripModel.fromJson(data['data'] as Map<String, dynamic>);
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Failed to update trip',
    );
  }

  /// DELETE /trips/:id — Soft delete trip
  Future<void> deleteTrip(String id) async {
    await _dio.delete('/trips/$id');
  }

  /// POST /trips/:id/itinerary — Add itinerary item
  Future<ItineraryItemModel> addItineraryItem(
    String tripId,
    AddItineraryItemRequest request,
  ) async {
    final response = await _dio.post(
      '/trips/$tripId/itinerary',
      data: request.toJson(),
    );
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return ItineraryItemModel.fromJson(
        data['data'] as Map<String, dynamic>,
      );
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Failed to add itinerary item',
    );
  }

  /// DELETE /trips/:id/itinerary/:itemId
  Future<void> deleteItineraryItem(String tripId, String itemId) async {
    await _dio.delete('/trips/$tripId/itinerary/$itemId');
  }

  /// POST /trips/:id/ai-plan — Generate AI plan preview
  Future<AiPlanPreviewModel> generateAiPlan(
    String tripId, {
    String? prompt,
  }) async {
    final response = await _dio.post(
      '/trips/$tripId/ai-plan',
      data: {
        if (prompt != null && prompt.isNotEmpty) 'additionalPrompt': prompt,
      },
      // Real LLM planning takes ~30 s; global timeout is 15 s. Stay above the
      // NestJS->FastAPI timeout (60 s) so server errors surface instead of timeouts.
      options: Options(
        sendTimeout: const Duration(seconds: 75),
        receiveTimeout: const Duration(seconds: 75),
      ),
    );
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return AiPlanPreviewModel.fromJson(
        data['data'] as Map<String, dynamic>,
      );
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Failed to parse AI plan preview',
    );
  }

  /// POST /trips/:id/itinerary/bulk — Atomic bulk save itinerary
  Future<TripModel> bulkSaveItinerary(
    String tripId,
    BulkSaveItineraryRequest request,
  ) async {
    final response = await _dio.post(
      '/trips/$tripId/itinerary/bulk',
      data: request.toJson(),
    );
    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] is Map<String, dynamic>) {
      return TripModel.fromJson(data['data'] as Map<String, dynamic>);
    }
    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      error: 'Failed to bulk save itinerary',
    );
  }
}
