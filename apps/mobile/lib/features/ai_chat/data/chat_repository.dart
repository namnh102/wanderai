import 'package:dio/dio.dart';
import '../../../core/constants/app_constants.dart';

class ChatRepository {
  // Gọi FastAPI AI service trực tiếp (tránh CORS qua NestJS proxy)
  Future<Map<String, dynamic>> sendMessage(String message, String? sessionId) async {
    try {
      final dio = Dio();
      dio.options.connectTimeout = const Duration(seconds: 30);
      dio.options.receiveTimeout = const Duration(seconds: 30);

      final response = await dio.post(
        '${AppConstants.aiBaseUrl}/chat',
        data: {
          'message': message,
          if (sessionId != null) 'session_id': sessionId,
        },
      );

      return {
        'reply': response.data['reply'] ?? 'Không có phản hồi',
        'session_id': response.data['session_id'],
      };
    } catch (e) {
      return {
        'reply': 'Xin lỗi, Wandy đang gặp sự cố kết nối. Vui lòng thử lại sau! 😊',
        'session_id': sessionId,
      };
    }
  }
}