import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../map/data/place_model.dart';

/// Repository for verified traveler reviews (`GET /reviews`, `POST /reviews`, `DELETE /reviews/:id`).
class ReviewRepository {
  final Dio _dio;

  ReviewRepository(this._dio);

  Future<List<PlaceReviewModel>> getByPlace(String placeId) async {
    final response = await _dio.get('/reviews', queryParameters: {
      'placeId': placeId,
      'limit': 20,
    });
    final data = response.data;
    final inner = data is Map ? (data['data'] ?? data) : data;
    final items = inner is Map ? (inner['items'] as List? ?? []) : const [];
    return items
        .whereType<Map<String, dynamic>>()
        .map(PlaceReviewModel.fromJson)
        .toList();
  }

  Future<PlaceReviewModel> createReview({
    required String placeId,
    required double rating,
    required String content,
  }) async {
    final response = await _dio.post('/reviews', data: {
      'placeId': placeId,
      'rating': rating,
      'content': content.trim(),
    });
    final data = response.data;
    final inner = data is Map ? (data['data'] ?? data) : data;
    return PlaceReviewModel.fromJson(Map<String, dynamic>.from(inner as Map));
  }
}

final reviewRepositoryProvider = Provider<ReviewRepository>((ref) {
  return ReviewRepository(ref.read(apiClientProvider));
});
