import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import 'recommendation_models.dart';

/// Human-readable failure raised by [RecommendationRepository].
/// [message] is always safe to show to the user (never a raw map/stack).
class RecommendationException implements Exception {
  final String message;
  final int? statusCode;
  const RecommendationException(this.message, {this.statusCode});

  @override
  String toString() => message;
}

/// Authenticated access to the NestJS REC-A endpoint.
///
/// Architecture: Flutter -> NestJS (JWT) -> PostgreSQL preferences -> FastAPI -> REC-A.
/// The mobile app never calls FastAPI directly and never ranks places itself.
class RecommendationRepository {
  final Dio _dio;

  RecommendationRepository(this._dio);

  static const defaultTopK = 10;
  static const defaultModel = 'rec-a1';

  Future<RecommendationResult> fetch({
    required String destination,
    int topK = defaultTopK,
    String model = defaultModel,
  }) async {
    try {
      final response = await _dio.get(
        '/places/recommendations',
        queryParameters: {
          'destination': destination,
          'topK': topK,
          'model': model,
        },
      );
      final data = response.data['data'] as Map<String, dynamic>;
      return RecommendationResult.fromJson(data);
    } on DioException catch (e) {
      throw RecommendationException(
        mapRecommendationError(e),
        statusCode: e.response?.statusCode,
      );
    } on RecommendationException {
      rethrow;
    } catch (_) {
      throw const RecommendationException(
        'Không đọc được dữ liệu gợi ý từ máy chủ. Vui lòng thử lại.',
      );
    }
  }

  /// Map transport/API errors to a readable Vietnamese message.
  /// Raw objects (`{detail: ...}`) are never surfaced.
  static String mapRecommendationError(DioException e) {
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout) {
      return 'Máy chủ phản hồi quá lâu. Vui lòng thử lại.';
    }
    if (e.type == DioExceptionType.connectionError) {
      return 'Không có kết nối mạng.';
    }
    final status = e.response?.statusCode;
    if (status == 401) {
      return 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
    }
    final readable = _readableMessage(e.response?.data);
    if (status == 400 || status == 422) {
      return readable ?? 'Yêu cầu gợi ý không hợp lệ.';
    }
    if (status == 503) {
      return readable ?? 'Dịch vụ gợi ý tạm thời không khả dụng. Vui lòng thử lại sau.';
    }
    return readable ?? 'Không thể tải gợi ý (lỗi ${status ?? 'không xác định'}). Vui lòng thử lại.';
  }

  static String? _readableMessage(dynamic data) {
    if (data is Map) {
      final msg = data['message'];
      if (msg is String && msg.trim().isNotEmpty) return msg;
      if (msg is List && msg.isNotEmpty && msg.first is String) {
        return msg.whereType<String>().join('; ');
      }
    }
    return null; // maps / unknown shapes are not shown raw
  }
}

final recommendationRepositoryProvider = Provider<RecommendationRepository>((ref) {
  final dio = ref.read(apiClientProvider);
  return RecommendationRepository(dio);
});
