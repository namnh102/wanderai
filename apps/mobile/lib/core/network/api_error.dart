import 'package:dio/dio.dart';

/// Parsed error details from NestJS `HttpExceptionFilter` responses and Dio
/// transport errors.
class ApiErrorDetails {
  final int? statusCode;
  final String? errorCode;
  final String? message;
  final bool isNetworkError;

  const ApiErrorDetails({
    this.statusCode,
    this.errorCode,
    this.message,
    this.isNetworkError = false,
  });

  bool get isTransientServerError =>
      statusCode == 502 || statusCode == 503 || statusCode == 504;

  bool get isOfflineOrTransient => isNetworkError || isTransientServerError;

  factory ApiErrorDetails.fromDioException(DioException e) {
    final isNetwork = e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout;

    final statusCode = e.response?.statusCode;
    final data = e.response?.data;

    String? errorCode;
    String? message;
    if (data is Map) {
      final rawCode = data['errorCode'];
      if (rawCode is String && rawCode.trim().isNotEmpty) {
        errorCode = rawCode.trim();
      }
      final rawMsg = data['message'];
      if (rawMsg is String && rawMsg.trim().isNotEmpty) {
        message = rawMsg.trim();
      } else if (rawMsg is List && rawMsg.isNotEmpty) {
        message = rawMsg.map((item) => item.toString().trim()).join(', ');
      }
    }

    return ApiErrorDetails(
      statusCode: statusCode,
      errorCode: errorCode,
      message: message,
      isNetworkError: isNetwork,
    );
  }
}
