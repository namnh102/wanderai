import 'package:dio/dio.dart';
import 'destination_model.dart';
import 'place_model.dart';

/// Repository for places API — calls NestJS :3000/places endpoints.
class PlaceRepository {
  final Dio _dio;

  PlaceRepository(this._dio);

  /// Fetch the destination list (`GET /destinations`).
  Future<List<DestinationModel>> getDestinations({int limit = 50}) async {
    final response =
        await _dio.get('/destinations', queryParameters: {'limit': limit});
    final data = response.data;
    if (data is Map<String, dynamic>) {
      final inner = data['data'] ?? data;
      final items = (inner is Map ? inner['items'] : inner) as List? ?? [];
      return items
          .map((e) => DestinationModel.fromJson(e as Map<String, dynamic>))
          .toList();
    }
    return [];
  }

  /// Fetch verified places with optional category / destination filter.
  Future<List<PlaceModel>> getPlaces({
    int page = 1,
    int limit = 50,
    String? search,
    String? category,
    String? destinationId,
    bool verifiedOnly = true,
  }) async {
    final response = await _dio.get('/places', queryParameters: {
      'page': page,
      'limit': limit,
      'verifiedOnly': verifiedOnly.toString(),
      if (search != null && search.isNotEmpty) 'search': search,
      if (category != null) 'category': category,
      if (destinationId != null) 'destinationId': destinationId,
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

/// Backend page-size ceiling for `GET /places` (W3-04 contract: 1..100).
const placesMaxPageSize = 100;

/// Reusable pagination helper. Defined as an extension (not an instance
/// method) so every [PlaceRepository] implementation, including test fakes,
/// gets it by only implementing [PlaceRepository.getPlaces].
extension PlaceRepositoryPaging on PlaceRepository {
  /// Walks `GET /places?destinationId=…&verifiedOnly=true&limit=100&page=N`
  /// until a short/empty page, de-duplicating by id.
  Future<List<PlaceModel>> getAllPlacesForDestination({
    required String destinationId,
    String? category,
    int pageSize = placesMaxPageSize,
    int maxPages = 50,
  }) async {
    final byId = <String, PlaceModel>{};
    for (var page = 1; page <= maxPages; page++) {
      final items = await getPlaces(
        page: page,
        limit: pageSize,
        destinationId: destinationId,
        category: category,
        verifiedOnly: true,
      );
      for (final p in items) {
        byId.putIfAbsent(p.id, () => p);
      }
      if (items.length < pageSize) break;
    }
    return byId.values.toList();
  }
}
