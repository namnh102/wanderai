import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/features/auth/data/auth_repository.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/home/presentation/home_screen.dart';

ResponseBody _jsonBody(int statusCode, Map<String, dynamic> body) {
  return ResponseBody.fromString(
    jsonEncode(body),
    statusCode,
    headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    },
  );
}

class _RefreshMockAdapter implements HttpClientAdapter {
  final bool refreshShouldFail;
  int refreshCalls = 0;
  final List<String> requestedPaths = [];
  final List<String?> authHeadersSeen = [];
  Map<String, dynamic>? lastRefreshPayload;

  _RefreshMockAdapter({this.refreshShouldFail = false});

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requestedPaths.add(options.path);
    authHeadersSeen.add(options.headers['Authorization'] as String?);

    if (options.path == '/auth/login') {
      return _jsonBody(401, {'message': 'Invalid credentials'});
    }

    if (options.path == '/auth/refresh') {
      refreshCalls++;
      if (options.data is Map) {
        lastRefreshPayload = Map<String, dynamic>.from(options.data as Map);
      }
      // Small async yield so concurrent 401 requests test single-flight lock.
      await Future<void>.delayed(const Duration(milliseconds: 25));
      if (refreshShouldFail) {
        return _jsonBody(401, {'message': 'Refresh token expired'});
      }
      return _jsonBody(200, {
        'success': true,
        'data': {
          'access_token': 'fresh-access',
          'refresh_token': 'fresh-refresh',
        },
      });
    }

    final auth = options.headers['Authorization'] as String?;
    if (auth == 'Bearer fresh-access') {
      return _jsonBody(200, {
        'success': true,
        'data': {'path': options.path, 'ok': true},
      });
    }

    return _jsonBody(401, {'message': 'Access token expired'});
  }

  @override
  void close({bool force = false}) {}
}

class _DelayedAuthRepository extends Fake implements AuthRepository {
  final Completer<bool> restoreCompleter;
  _DelayedAuthRepository(this.restoreCompleter);

  @override
  Future<bool> restoreSession() => restoreCompleter.future;
}

class _PreLoginCheckAdapter implements HttpClientAdapter {
  final List<String> paths = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    paths.add(options.path);
    if (options.path == '/destinations' || options.path == '/places') {
      return _jsonBody(200, {
        'success': true,
        'data': {'items': <dynamic>[]},
      });
    }
    if (options.path == '/users/me') {
      return _jsonBody(200, {
        'success': true,
        'data': {
          'profile': {'displayName': 'Tester'},
          'preferences': {'interests': <String>[]},
        },
      });
    }
    return _jsonBody(200, {'success': true, 'data': {}});
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('JWT Refresh Interceptor', () {
    test('single-flights concurrent 401s, rotates tokens, and retries both requests',
        () async {
      SharedPreferences.setMockInitialValues({
        'access_token': 'expired-access',
        'refresh_token': 'valid-refresh',
      });

      var sessionExpiredCalls = 0;
      final adapter = _RefreshMockAdapter();
      final dio = createApiClient(
        baseUrlOverride: 'http://localhost:3000/api/v1',
        onSessionExpired: () => sessionExpiredCalls++,
      )..httpClientAdapter = adapter;

      final responses = await Future.wait([
        dio.get<dynamic>('/users/me'),
        dio.get<dynamic>('/trips'),
      ]);

      expect(responses[0].statusCode, 200);
      expect(responses[1].statusCode, 200);
      expect(adapter.refreshCalls, 1);
      expect(adapter.lastRefreshPayload, {'refresh_token': 'valid-refresh'});
      expect(sessionExpiredCalls, 0);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('access_token'), 'fresh-access');
      expect(prefs.getString('refresh_token'), 'fresh-refresh');
    });

    test('clears tokens and triggers session expiration when refresh fails', () async {
      SharedPreferences.setMockInitialValues({
        'access_token': 'expired-access',
        'refresh_token': 'revoked-refresh',
      });

      var sessionExpiredCalls = 0;
      final adapter = _RefreshMockAdapter(refreshShouldFail: true);
      final dio = createApiClient(
        baseUrlOverride: 'http://localhost:3000/api/v1',
        onSessionExpired: () => sessionExpiredCalls++,
      )..httpClientAdapter = adapter;

      await expectLater(
        () => dio.get<dynamic>('/users/me'),
        throwsA(isA<DioException>()),
      );

      expect(adapter.refreshCalls, 1);
      expect(sessionExpiredCalls, 1);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('access_token'), isNull);
      expect(prefs.getString('refresh_token'), isNull);
    });

    test('never refreshes or loops on public auth endpoint 401', () async {
      SharedPreferences.setMockInitialValues({
        'access_token': 'stale-access',
        'refresh_token': 'stale-refresh',
      });

      var sessionExpiredCalls = 0;
      final adapter = _RefreshMockAdapter(refreshShouldFail: true);
      final dio = createApiClient(
        baseUrlOverride: 'http://localhost:3000/api/v1',
        onSessionExpired: () => sessionExpiredCalls++,
      )..httpClientAdapter = adapter;

      await expectLater(
        () => dio.post<dynamic>('/auth/login', data: {'email': 'a@b.c', 'password': 'x'}),
        throwsA(isA<DioException>()),
      );

      expect(adapter.refreshCalls, 0);
      expect(sessionExpiredCalls, 0);
      expect(adapter.requestedPaths, ['/auth/login']);
      expect(adapter.authHeadersSeen.first, isNull);
    });

    test('syncs AuthNotifier state to unauthenticated on session expiration signal',
        () async {
      SharedPreferences.setMockInitialValues({
        'access_token': 'expired-access',
        'refresh_token': 'revoked-refresh',
      });

      final adapter = _RefreshMockAdapter(refreshShouldFail: true);
      final container = ProviderContainer(
        overrides: [
          apiClientProvider.overrideWith((ref) {
            return createApiClient(
              baseUrlOverride: 'http://localhost:3000/api/v1',
              onSessionExpired: () {
                ref.read(authSessionExpiredSignalProvider.notifier).state++;
              },
            )..httpClientAdapter = adapter;
          }),
        ],
      );
      addTearDown(container.dispose);

      // Start AuthNotifier._init() before awaiting its completion.
      expect(container.read(authProvider).status, AuthStatus.unknown);
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(container.read(authProvider).status, AuthStatus.authenticated);

      final dio = container.read(apiClientProvider);
      await expectLater(
        () => dio.get<dynamic>('/users/me'),
        throwsA(isA<DioException>()),
      );

      expect(container.read(authProvider).status, AuthStatus.unauthenticated);
      expect(
        container.read(authProvider).errorMessage,
        'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
      );
    });
  });

  group('Pre-login ShellRoute /users/me guard', () {
    testWidgets('does not mount HomeScreen or call /users/me while AuthStatus.unknown',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final restoreCompleter = Completer<bool>();
      final adapter = _PreLoginCheckAdapter();

      final container = ProviderContainer(
        overrides: [
          authRepositoryProvider.overrideWithValue(
            _DelayedAuthRepository(restoreCompleter),
          ),
          apiClientProvider.overrideWithValue(
            createApiClient(baseUrlOverride: 'http://localhost:3000/api/v1')
              ..httpClientAdapter = adapter,
          ),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await tester.pump();

      expect(container.read(authProvider).status, AuthStatus.unknown);
      expect(find.byType(HomeScreen), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(adapter.paths, isNot(contains('/users/me')));

      restoreCompleter.complete(false);
      await tester.pumpAndSettle();

      expect(container.read(authProvider).status, AuthStatus.unauthenticated);
      expect(find.byType(HomeScreen), findsNothing);
      expect(adapter.paths, isNot(contains('/users/me')));
    });
  });
}
