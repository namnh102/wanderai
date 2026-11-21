import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../constants/app_constants.dart';

const _accessTokenKey = 'access_token';
const _refreshTokenKey = 'refresh_token';
const _retriedRefreshExtraKey = '_retriedAuthRefresh';
const _publicAuthPaths = {'/auth/login', '/auth/register', '/auth/refresh'};

/// Notifies listeners whenever automatic JWT refresh fails cleanly on 401.
final authSessionExpiredSignalProvider = StateProvider<int>((ref) => 0);

bool _isPublicAuthPath(String path) {
  final normalized = path.split('?').first;
  return _publicAuthPaths.any((p) => normalized == p || normalized.endsWith(p));
}

class _JwtAuthInterceptor extends Interceptor {
  final Dio _dio;
  final VoidCallback? _onSessionExpired;

  Completer<String?>? _refreshCompleter;

  _JwtAuthInterceptor(this._dio, {VoidCallback? onSessionExpired})
      : _onSessionExpired = onSessionExpired;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (!_isPublicAuthPath(options.path)) {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString(_accessTokenKey);
      if (token != null && token.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final req = err.requestOptions;
    final statusCode = err.response?.statusCode;
    final alreadyRetried = req.extra[_retriedRefreshExtraKey] == true;

    if (statusCode != 401 ||
        alreadyRetried ||
        _isPublicAuthPath(req.path)) {
      handler.next(err);
      return;
    }

    final newAccessToken = await _refreshSingleFlight();
    if (newAccessToken == null || newAccessToken.isEmpty) {
      handler.next(err);
      return;
    }

    final retryOptions = req.copyWith(
      headers: {
        ...req.headers,
        'Authorization': 'Bearer $newAccessToken',
      },
      extra: {
        ...req.extra,
        _retriedRefreshExtraKey: true,
      },
    );

    try {
      final response = await _dio.fetch<dynamic>(retryOptions);
      handler.resolve(response);
    } on DioException catch (retryErr) {
      handler.next(retryErr);
    } catch (_) {
      handler.next(err);
    }
  }

  Future<String?> _refreshSingleFlight() async {
    final inFlight = _refreshCompleter;
    if (inFlight != null) {
      return inFlight.future;
    }

    final completer = Completer<String?>();
    _refreshCompleter = completer;

    try {
      final prefs = await SharedPreferences.getInstance();
      final refreshToken = prefs.getString(_refreshTokenKey);
      if (refreshToken == null || refreshToken.trim().isEmpty) {
        await _clearTokensAndNotify(prefs);
        completer.complete(null);
        return null;
      }

      // Dedicated Dio sharing adapter avoids re-entering _JwtAuthInterceptor.
      final refreshDio = Dio(
        BaseOptions(
          baseUrl: _dio.options.baseUrl,
          connectTimeout: _dio.options.connectTimeout,
          receiveTimeout: _dio.options.receiveTimeout,
          headers: const {'Content-Type': 'application/json'},
        ),
      )..httpClientAdapter = _dio.httpClientAdapter;

      final response = await refreshDio.post<dynamic>(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
      );

      final envelope = response.data;
      final data = envelope is Map ? envelope['data'] : null;
      final nextAccess =
          data is Map ? (data['access_token'] as String?)?.trim() : null;
      final nextRefresh =
          data is Map ? (data['refresh_token'] as String?)?.trim() : null;

      if (nextAccess == null ||
          nextAccess.isEmpty ||
          nextRefresh == null ||
          nextRefresh.isEmpty) {
        await _clearTokensAndNotify(prefs);
        completer.complete(null);
        return null;
      }

      await prefs.setString(_accessTokenKey, nextAccess);
      await prefs.setString(_refreshTokenKey, nextRefresh);
      completer.complete(nextAccess);
      return nextAccess;
    } catch (_) {
      final prefs = await SharedPreferences.getInstance();
      await _clearTokensAndNotify(prefs);
      completer.complete(null);
      return null;
    } finally {
      _refreshCompleter = null;
    }
  }

  Future<void> _clearTokensAndNotify(SharedPreferences prefs) async {
    final hadToken = prefs.getString(_accessTokenKey) != null ||
        prefs.getString(_refreshTokenKey) != null;
    await prefs.remove(_accessTokenKey);
    await prefs.remove(_refreshTokenKey);
    if (hadToken) {
      _onSessionExpired?.call();
    }
  }
}

/// Builds a configured [Dio] client targeting the NestJS backend gateway.
Dio createApiClient({
  String? baseUrlOverride,
  bool isReleaseMode = kReleaseMode,
  bool isProfileMode = kProfileMode,
  VoidCallback? onSessionExpired,
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

  dio.interceptors.add(
    _JwtAuthInterceptor(dio, onSessionExpired: onSessionExpired),
  );

  return dio;
}

final apiClientProvider = Provider<Dio>((ref) {
  return createApiClient(
    onSessionExpired: () {
      ref.read(authSessionExpiredSignalProvider.notifier).state++;
    },
  );
});
