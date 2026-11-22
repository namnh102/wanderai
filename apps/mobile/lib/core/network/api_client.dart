import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../constants/app_constants.dart';

const _accessTokenKey = 'access_token';
const _refreshTokenKey = 'refresh_token';
const _retriedRefreshExtraKey = '_retriedAuthRefresh';
const _requestEpochExtraKey = '_authSessionEpoch';
const _publicAuthPaths = {'/auth/login', '/auth/register', '/auth/refresh'};

/// Notifies listeners whenever automatic JWT refresh fails cleanly on 401/403.
final authSessionExpiredSignalProvider = StateProvider<int>((ref) => 0);

/// Monotonic auth session generation used to bind outbound requests, in-flight
/// JWT refreshes, and single retries to the session that originated them.
class SessionEpochController {
  int _epoch = 0;

  int get current => _epoch;

  int advance() {
    _epoch++;
    return _epoch;
  }
}

final sessionEpochControllerProvider =
    Provider<SessionEpochController>((ref) => SessionEpochController());

bool _isPublicAuthPath(String path) {
  final normalized = path.split('?').first;
  return _publicAuthPaths.any((p) => normalized == p || normalized.endsWith(p));
}

class _JwtAuthInterceptor extends Interceptor {
  final Dio _dio;
  final SessionEpochController _sessionEpoch;
  final VoidCallback? _onSessionExpired;

  final Map<int, Completer<String?>> _inFlightByEpoch = {};

  _JwtAuthInterceptor(
    this._dio, {
    required SessionEpochController sessionEpoch,
    VoidCallback? onSessionExpired,
  })  : _sessionEpoch = sessionEpoch,
        _onSessionExpired = onSessionExpired;

  bool _isStale(int epoch) => _sessionEpoch.current != epoch;

  DioException _staleSessionException(RequestOptions req) => DioException(
        requestOptions: req,
        type: DioExceptionType.cancel,
        message: 'Auth session changed before request completed.',
      );

  bool _isInvalidRefreshCredential(DioException err) {
    final status = err.response?.statusCode;
    return status == 401 || status == 403;
  }

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (_isPublicAuthPath(options.path)) {
      handler.next(options);
      return;
    }

    // Retry path already carries the exact refreshed token for its originating epoch;
    // never swap in a newer session's stored token from SharedPreferences.
    final boundEpoch = options.extra[_requestEpochExtraKey] as int?;
    if (boundEpoch != null) {
      if (_isStale(boundEpoch)) {
        handler.reject(_staleSessionException(options));
        return;
      }
      handler.next(options);
      return;
    }

    final originEpoch = _sessionEpoch.current;
    options.extra[_requestEpochExtraKey] = originEpoch;

    final prefs = await SharedPreferences.getInstance();
    if (_isStale(originEpoch)) {
      handler.reject(_staleSessionException(options));
      return;
    }

    final token = prefs.getString(_accessTokenKey);
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
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
    final boundEpoch = req.extra[_requestEpochExtraKey] as int?;

    // Never refresh or retry a stale session's delayed error under a newer session.
    if (boundEpoch != null && _isStale(boundEpoch)) {
      handler.reject(_staleSessionException(req));
      return;
    }

    final originEpoch = boundEpoch ?? _sessionEpoch.current;

    if (statusCode != 401 ||
        alreadyRetried ||
        _isPublicAuthPath(req.path)) {
      handler.next(err);
      return;
    }

    final newAccessToken = await _refreshSingleFlight(originEpoch);
    if (_isStale(originEpoch)) {
      handler.reject(_staleSessionException(req));
      return;
    }

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
        _requestEpochExtraKey: originEpoch,
      },
    );

    try {
      final response = await _dio.fetch<dynamic>(retryOptions);
      if (_isStale(originEpoch)) {
        handler.reject(_staleSessionException(req));
        return;
      }
      handler.resolve(response);
    } on DioException catch (retryErr) {
      if (_isStale(originEpoch)) {
        handler.reject(_staleSessionException(req));
        return;
      }
      handler.next(retryErr);
    } catch (_) {
      handler.next(err);
    }
  }

  Future<String?> _refreshSingleFlight(int expectedEpoch) async {
    if (_isStale(expectedEpoch)) {
      return null;
    }

    final inFlight = _inFlightByEpoch[expectedEpoch];
    if (inFlight != null) {
      return inFlight.future;
    }

    final completer = Completer<String?>();
    _inFlightByEpoch[expectedEpoch] = completer;

    try {
      final prefs = await SharedPreferences.getInstance();
      if (_isStale(expectedEpoch)) {
        completer.complete(null);
        return null;
      }

      final refreshToken = prefs.getString(_refreshTokenKey);
      if (refreshToken == null || refreshToken.trim().isEmpty) {
        await _clearTokensAndNotifyIfSameEpoch(prefs, expectedEpoch);
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

      if (_isStale(expectedEpoch)) {
        completer.complete(null);
        return null;
      }

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
        await _clearTokensAndNotifyIfSameEpoch(prefs, expectedEpoch);
        completer.complete(null);
        return null;
      }

      if (_isStale(expectedEpoch)) {
        completer.complete(null);
        return null;
      }

      await prefs.setString(_accessTokenKey, nextAccess);
      if (_isStale(expectedEpoch)) {
        completer.complete(null);
        return null;
      }
      await prefs.setString(_refreshTokenKey, nextRefresh);

      completer.complete(nextAccess);
      return nextAccess;
    } on DioException catch (refreshErr) {
      if (_isStale(expectedEpoch)) {
        completer.complete(null);
        return null;
      }
      if (_isInvalidRefreshCredential(refreshErr)) {
        final prefs = await SharedPreferences.getInstance();
        await _clearTokensAndNotifyIfSameEpoch(prefs, expectedEpoch);
      }
      // Transient timeout/connection/5xx failures preserve tokens without logging out.
      completer.complete(null);
      return null;
    } catch (_) {
      // Non-credential failure: preserve session if same epoch, discard if stale.
      completer.complete(null);
      return null;
    } finally {
      _inFlightByEpoch.remove(expectedEpoch);
    }
  }

  Future<void> _clearTokensAndNotifyIfSameEpoch(
    SharedPreferences prefs,
    int expectedEpoch,
  ) async {
    if (_isStale(expectedEpoch)) {
      return;
    }
    final hadToken = prefs.getString(_accessTokenKey) != null ||
        prefs.getString(_refreshTokenKey) != null;
    await prefs.remove(_accessTokenKey);
    await prefs.remove(_refreshTokenKey);
    if (_isStale(expectedEpoch)) {
      return;
    }
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
  SessionEpochController? sessionEpoch,
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
    _JwtAuthInterceptor(
      dio,
      sessionEpoch: sessionEpoch ?? SessionEpochController(),
      onSessionExpired: onSessionExpired,
    ),
  );

  return dio;
}

final apiClientProvider = Provider<Dio>((ref) {
  final epochController = ref.read(sessionEpochControllerProvider);
  return createApiClient(
    sessionEpoch: epochController,
    onSessionExpired: () {
      ref.read(authSessionExpiredSignalProvider.notifier).state++;
    },
  );
});
