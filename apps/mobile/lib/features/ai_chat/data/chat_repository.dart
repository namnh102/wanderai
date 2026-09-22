import 'package:dio/dio.dart';
import '../../../core/network/api_endpoints.dart';
import '../../../core/constants/app_constants.dart';
import 'chat_model.dart';

class ChatRepository {
  Future<ChatResponse> sendMessage(String message, String? sessionId) async {
    try {
      final dio = Dio(BaseOptions(baseUrl: AppConstants.aiBaseUrl)); // specific URL
      final res = await dio.post(ApiEndpoints.aiChat, data: {
        'message': message,
        if (sessionId != null) 'sessionId': sessionId,
      });
      return ChatResponse.fromJson(res.data);
    } catch (e) {
      return ChatResponse(reply: 'Xin lỗi, Wandy đang gặp sự cố. Vui lòng thử lại sau.', sessionId: sessionId ?? 'new');
    }
  }
}