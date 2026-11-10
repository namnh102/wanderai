import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../constants/app_constants.dart';

/// Builds a configured [Dio] client targeting the NestJS backend gateway.
Dio createApiClient({
  String? baseUrlOverride,
  bool isReleaseMode = kReleaseMode,
  bool isProfileMode = kProfileMode,
}) {
  final resolvedBaseUrl = AppConstants.resolveApiBaseUrl(
    rawUrl: baseUrlOverride,
    isReleaseMode: isReleaseMode,
    isProfileMode: isProfileMode,
  );

  final dio = Dio(BaseOptions(
    baseUrl: resolvedBaseUrl,
    connectTimeout: const Duration(seconds: 15),
    receiveTimeout: const Duration(seconds: 15),
    headers: {'Content-Type': 'application/json'},
  ));

  dio.interceptors.add(InterceptorsWrapper(
    onRequest: (options, handler) async {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('access_token');
      if (token != null) {
        options.headers['Authorization'] = 'Bearer $token';
      }
      handler.next(options);
    },
    onError: (error, handler) {
      handler.next(error);
    },
  ));

  return dio;
}

final apiClientProvider = Provider<Dio>((ref) {
  return createApiClient();
});
