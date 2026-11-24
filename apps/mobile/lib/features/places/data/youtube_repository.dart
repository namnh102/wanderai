import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import 'youtube_update_model.dart';

/// Repository for `DYNAMIC_SOCIAL_FRESHNESS_LAYER` YouTube updates:
/// - `GET /places/:id/youtube-updates`
/// - `GET /destinations/:idOrSlug/youtube-updates`
class YoutubeRepository {
  final Dio _dio;

  YoutubeRepository(this._dio);

  Future<YoutubeUpdatesEnvelope> getPlaceUpdates(
    String placeId, {
    int limit = 10,
  }) async {
    final response = await _dio.get(
      '/places/$placeId/youtube-updates',
      queryParameters: {'limit': limit},
    );
    return _parseEnvelope(response.data);
  }

  Future<YoutubeUpdatesEnvelope> getDestinationUpdates(
    String idOrSlug, {
    int limit = 10,
    String? scope,
  }) async {
    final response = await _dio.get(
      '/destinations/$idOrSlug/youtube-updates',
      queryParameters: {
        'limit': limit,
        if (scope != null) 'scope': scope,
      },
    );
    return _parseEnvelope(response.data);
  }

  YoutubeUpdatesEnvelope _parseEnvelope(dynamic raw) {
    final inner = raw is Map ? (raw['data'] ?? raw) : raw;
    if (inner is! Map) {
      throw FormatException(
        'Unexpected YouTube updates response payload: ${raw.runtimeType}',
      );
    }
    return YoutubeUpdatesEnvelope.fromJson(Map<String, dynamic>.from(inner));
  }
}

final youtubeRepositoryProvider = Provider<YoutubeRepository>((ref) {
  return YoutubeRepository(ref.watch(apiClientProvider));
});
