import 'package:dio/dio.dart';
import 'chat_models.dart';

/// Repository for AI Chat communicating through NestJS AI Proxy.
class ChatRepository {
  final Dio _dio;

  ChatRepository(this._dio);

  /// Send message to Wandy via NestJS `/ai/chat` proxy.
  /// Uses a dedicated 35s timeout for AI model inference.
  Future<ChatResponse> sendMessage(ChatRequest request) async {
    final response = await _dio.post(
      '/ai/chat',
      data: request.toJson(),
      options: Options(
        sendTimeout: const Duration(seconds: 35),
        receiveTimeout: const Duration(seconds: 35),
      ),
    );

    final data = response.data;
    if (data is Map<String, dynamic> && data['data'] != null) {
      return ChatResponse.fromJson(data['data'] as Map<String, dynamic>);
    }

    throw DioException(
      requestOptions: response.requestOptions,
      response: response,
      type: DioExceptionType.badResponse,
      error: 'Invalid response format from AI service',
    );
  }

  /// Clear server-side chat history for [sessionId] via NestJS `DELETE /ai/chat/:sessionId`.
  Future<void> clearSession(String sessionId) async {
    final trimmed = sessionId.trim();
    if (trimmed.isEmpty) return;
    await _dio.delete(
      '/ai/chat/${Uri.encodeComponent(trimmed)}',
      options: Options(
        sendTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 10),
      ),
    );
  }
}
