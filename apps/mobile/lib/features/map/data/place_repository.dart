import 'package:dio/dio.dart';
import 'place_model.dart';

/// Repository for places API — calls NestJS :3000/places endpoints.
class PlaceRepository {
  final Dio _dio;

  PlaceRepository(this._dio);

  /// Fetch verified places with optional category filter.
  Future<List<PlaceModel>> getPlaces({
    int page = 1,
    int limit = 50,
    String? search,
    String? category,
    bool verifiedOnly = true,
  }) async {
    final response = await _dio.get('/places', queryParameters: {
      'page': page,
      'limit': limit,
      'verifiedOnly': verifiedOnly.toString(),
      if (search != null && search.isNotEmpty) 'search': search,
      if (category != null) 'category': category,
    });

    final data = response.data;
    if (data is Map<String, dynamic>) {
      final inner = data['data'] ?? data;
      final items = inner['items'] as List? ?? [];
      return items
          .map((e) => PlaceModel.fromJson(e as Map<String, dynamic>))
          .toList();
    }
    return [];
  }

  /// Fetch nearby places using PostGIS spatial query.
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10,
    int limit = 50,
    bool verifiedOnly = true,
  }) async {
    final response = await _dio.get('/places/nearby', queryParameters: {
      'lat': lat,
      'lng': lng,
      'radius': radiusKm,
      'limit': limit,
      'verifiedOnly': verifiedOnly.toString(),
    });

    final data = response.data;
    List items;
    if (data is Map<String, dynamic>) {
      items = data['data'] as List? ?? [];
    } else if (data is List) {
      items = data;
    } else {
      return [];
    }

    return items
        .map((e) => PlaceModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Fetch single place detail.
  Future<PlaceModel> getPlaceById(String id) async {
    final response = await _dio.get('/places/$id');
    final data = response.data;
    final inner =
        data is Map<String, dynamic> ? (data['data'] ?? data) : data;
    return PlaceModel.fromJson(inner as Map<String, dynamic>);
  }
}
