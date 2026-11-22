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
import 'package:wanderai_mobile/features/profile/providers/profile_provider.dart';
import 'package:wanderai_mobile/features/trips/providers/trip_provider.dart';

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

class _ControllableAuthAdapter implements HttpClientAdapter {
  final Future<ResponseBody> Function(RequestOptions options)? onRequest;
  final List<(String path, String? authHeader)> recordedRequests = [];
  int refreshCalls = 0;
  final List<Map<String, dynamic>> refreshPayloads = [];

  _ControllableAuthAdapter({this.onRequest});

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    recordedRequests.add((options.path, options.headers['Authorization'] as String?));
    if (options.path == '/auth/refresh') {
      refreshCalls++;
      if (options.data is Map) {
        refreshPayloads.add(Map<String, dynamic>.from(options.data as Map));
      }
    }
    if (onRequest != null) {
      return onRequest!(options);
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

  group('PR #99 P1 JWT Session Isolation & Epoch Gating', () {
    test(
        'stale refresh success after logout never writes tokens back or retries under logged-out state',
        () async {
      SharedPreferences.setMockInitialValues({
        'access_token': 'access-a',
        'refresh_token': 'refresh-a',
      });

      final epoch = SessionEpochController();
      final refreshGate = Completer<ResponseBody>();
      var sessionExpiredCalls = 0;

      final adapter = _ControllableAuthAdapter(
        onRequest: (options) async {
          if (options.path == '/auth/refresh') {
            return refreshGate.future;
          }
          if (options.headers['Authorization'] == 'Bearer access-a') {
            return _jsonBody(401, {'message': 'Expired access-a'});
          }
          return _jsonBody(200, {'success': true, 'data': {}});
        },
      );

      final dio = createApiClient(
        baseUrlOverride: 'http://localhost:3000/api/v1',
        sessionEpoch: epoch,
        onSessionExpired: () => sessionExpiredCalls++,
      )..httpClientAdapter = adapter;

      final requestFuture = dio.get<dynamic>('/users/me');
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(adapter.refreshCalls, 1);

      // Logout happens while /auth/refresh is in flight.
      epoch.advance();
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('access_token');
      await prefs.remove('refresh_token');

      refreshGate.complete(
        _jsonBody(200, {
          'success': true,
          'data': {
            'access_token': 'fresh-a-late',
            'refresh_token': 'fresh-refresh-a-late',
          },
        }),
      );

      await expectLater(
        requestFuture,
        throwsA(isA<DioException>().having((e) => e.type, 'type', DioExceptionType.cancel)),
      );

      expect(prefs.getString('access_token'), isNull);
      expect(prefs.getString('refresh_token'), isNull);
      expect(sessionExpiredCalls, 0);
      expect(
        adapter.recordedRequests.where((r) => r.$2 == 'Bearer fresh-a-late'),
        isEmpty,
      );
    });

    test(
        'stale refresh 401 failure after logout never fires onSessionExpired',
        () async {
      SharedPreferences.setMockInitialValues({
        'access_token': 'access-a',
        'refresh_token': 'refresh-a',
      });

      final epoch = SessionEpochController();
      final refreshGate = Completer<ResponseBody>();
      var sessionExpiredCalls = 0;

      final adapter = _ControllableAuthAdapter(
        onRequest: (options) async {
          if (options.path == '/auth/refresh') {
            return refreshGate.future;
          }
          return _jsonBody(401, {'message': 'Expired'});
        },
      );

      final dio = createApiClient(
        baseUrlOverride: 'http://localhost:3000/api/v1',
        sessionEpoch: epoch,
        onSessionExpired: () => sessionExpiredCalls++,
      )..httpClientAdapter = adapter;

      final requestFuture = dio.get<dynamic>('/users/me');
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(adapter.refreshCalls, 1);

      epoch.advance();
      refreshGate.complete(_jsonBody(401, {'message': 'Revoked'}));

      await expectLater(
        requestFuture,
        throwsA(isA<DioException>().having((e) => e.type, 'type', DioExceptionType.cancel)),
      );

      expect(sessionExpiredCalls, 0);
      expect(adapter.refreshCalls, 1);
    });

    test(
        'Account A -> Account B switch while A refresh pending (both late 200 and late 401) never corrupts B tokens',
        () async {
      for (final lateFailure in [false, true]) {
        SharedPreferences.setMockInitialValues({
          'access_token': 'access-a',
          'refresh_token': 'refresh-a',
        });

        final epoch = SessionEpochController();
        final refreshGateA = Completer<ResponseBody>();
        var sessionExpiredCalls = 0;

        final adapter = _ControllableAuthAdapter(
          onRequest: (options) async {
            if (options.path == '/auth/refresh') {
              return refreshGateA.future;
            }
            final auth = options.headers['Authorization'] as String?;
            if (auth == 'Bearer access-b') {
              return _jsonBody(200, {'success': true, 'data': {'account': 'B'}});
            }
            return _jsonBody(401, {'message': 'Expired A'});
          },
        );

        final dio = createApiClient(
          baseUrlOverride: 'http://localhost:3000/api/v1',
          sessionEpoch: epoch,
          onSessionExpired: () => sessionExpiredCalls++,
        )..httpClientAdapter = adapter;

        final requestA = dio.get<dynamic>('/users/me');
        await Future<void>.delayed(const Duration(milliseconds: 20));
        expect(adapter.refreshCalls, 1);

        // Switch to Account B while A's refresh is still pending.
        epoch.advance();
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString('access_token', 'access-b');
        await prefs.setString('refresh_token', 'refresh-b');

        // Late A refresh finishes with either 200 fresh-a or 401 revoked.
        refreshGateA.complete(
          lateFailure
              ? _jsonBody(401, {'message': 'Revoked A'})
              : _jsonBody(200, {
                  'success': true,
                  'data': {
                    'access_token': 'fresh-a',
                    'refresh_token': 'fresh-refresh-a',
                  },
                }),
        );

        await expectLater(requestA, throwsA(isA<DioException>()));

        expect(prefs.getString('access_token'), 'access-b');
        expect(prefs.getString('refresh_token'), 'refresh-b');
        expect(sessionExpiredCalls, 0);

        final responseB = await dio.get<dynamic>('/users/me');
        expect(responseB.statusCode, 200);
        expect(adapter.recordedRequests.last, ('/users/me', 'Bearer access-b'));
      }
    });

    test(
        'delayed 401 from Account A arriving after switch to Account B does not trigger refresh or retry under B',
        () async {
      SharedPreferences.setMockInitialValues({
        'access_token': 'access-a',
        'refresh_token': 'refresh-a',
      });

      final epoch = SessionEpochController();
      final responseGateA = Completer<ResponseBody>();
      var sessionExpiredCalls = 0;

      final adapter = _ControllableAuthAdapter(
        onRequest: (options) async {
          if (options.headers['Authorization'] == 'Bearer access-a') {
            return responseGateA.future;
          }
          return _jsonBody(200, {'success': true, 'data': {'ok': true}});
        },
      );

      final dio = createApiClient(
        baseUrlOverride: 'http://localhost:3000/api/v1',
        sessionEpoch: epoch,
        onSessionExpired: () => sessionExpiredCalls++,
      )..httpClientAdapter = adapter;

      final requestA = dio.get<dynamic>('/users/me');
      await Future<void>.delayed(const Duration(milliseconds: 20));

      // Account B signs in while A's request is still in-flight on the wire.
      epoch.advance();
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('access_token', 'access-b');
      await prefs.setString('refresh_token', 'refresh-b');

      // Server finally returns 401 to A's stale request.
      responseGateA.complete(_jsonBody(401, {'message': 'A expired'}));

      await expectLater(
        requestA,
        throwsA(isA<DioException>().having((e) => e.type, 'type', DioExceptionType.cancel)),
      );

      expect(adapter.refreshCalls, 0);
      expect(sessionExpiredCalls, 0);
      expect(prefs.getString('access_token'), 'access-b');
      expect(prefs.getString('refresh_token'), 'refresh-b');
      expect(
        adapter.recordedRequests.where((r) => r.$2 == 'Bearer access-b'),
        isEmpty,
      );
    });

    test(
        'transient refresh errors (connectionTimeout, connectionError, 503) keep tokens intact without logout; 403 invalidates',
        () async {
      for (final mode in ['timeout', 'connectionError', '503']) {
        SharedPreferences.setMockInitialValues({
          'access_token': 'expired-access',
          'refresh_token': 'valid-refresh',
        });

        var sessionExpiredCalls = 0;
        final adapter = _ControllableAuthAdapter(
          onRequest: (options) async {
            if (options.path == '/auth/refresh') {
              if (mode == 'timeout') {
                throw DioException(
                  requestOptions: options,
                  type: DioExceptionType.connectionTimeout,
                );
              }
              if (mode == 'connectionError') {
                throw DioException(
                  requestOptions: options,
                  type: DioExceptionType.connectionError,
                );
              }
              return _jsonBody(503, {'message': 'Service temporarily unavailable'});
            }
            return _jsonBody(401, {'message': 'Access token expired'});
          },
        );

        final container = ProviderContainer(
          overrides: [
            apiClientProvider.overrideWith((ref) {
              final epoch = ref.read(sessionEpochControllerProvider);
              return createApiClient(
                baseUrlOverride: 'http://localhost:3000/api/v1',
                sessionEpoch: epoch,
                onSessionExpired: () {
                  sessionExpiredCalls++;
                  ref.read(authSessionExpiredSignalProvider.notifier).state++;
                },
              )..httpClientAdapter = adapter;
            }),
          ],
        );
        addTearDown(container.dispose);

        expect(container.read(authProvider).status, AuthStatus.unknown);
        await Future<void>.delayed(const Duration(milliseconds: 20));
        expect(container.read(authProvider).status, AuthStatus.authenticated);

        final dio = container.read(apiClientProvider);
        await expectLater(() => dio.get<dynamic>('/users/me'), throwsA(isA<DioException>()));

        final prefs = await SharedPreferences.getInstance();
        expect(prefs.getString('access_token'), 'expired-access');
        expect(prefs.getString('refresh_token'), 'valid-refresh');
        expect(sessionExpiredCalls, 0);
        expect(container.read(authProvider).status, AuthStatus.authenticated);
      }

      // Contrast with explicit 403 invalid refresh credential -> clears tokens and signals expiry.
      SharedPreferences.setMockInitialValues({
        'access_token': 'expired-access',
        'refresh_token': 'forbidden-refresh',
      });
      var expired403 = 0;
      final adapter403 = _ControllableAuthAdapter(
        onRequest: (options) async {
          if (options.path == '/auth/refresh') {
            return _jsonBody(403, {'message': 'Refresh token forbidden'});
          }
          return _jsonBody(401, {'message': 'Access token expired'});
        },
      );
      final dio403 = createApiClient(
        baseUrlOverride: 'http://localhost:3000/api/v1',
        onSessionExpired: () => expired403++,
      )..httpClientAdapter = adapter403;

      await expectLater(() => dio403.get<dynamic>('/users/me'), throwsA(isA<DioException>()));
      final prefs403 = await SharedPreferences.getInstance();
      expect(prefs403.getString('access_token'), isNull);
      expect(prefs403.getString('refresh_token'), isNull);
      expect(expired403, 1);
    });

    test(
        'persistent 401 even after fresh token performs single refresh and at most one retry per request',
        () async {
      SharedPreferences.setMockInitialValues({
        'access_token': 'expired-access',
        'refresh_token': 'valid-refresh',
      });

      final adapter = _ControllableAuthAdapter(
        onRequest: (options) async {
          if (options.path == '/auth/refresh') {
            return _jsonBody(200, {
              'success': true,
              'data': {
                'access_token': 'fresh-access',
                'refresh_token': 'fresh-refresh',
              },
            });
          }
          return _jsonBody(401, {'message': 'Still unauthorized'});
        },
      );

      final dio = createApiClient(
        baseUrlOverride: 'http://localhost:3000/api/v1',
      )..httpClientAdapter = adapter;

      await expectLater(() => dio.get<dynamic>('/users/me'), throwsA(isA<DioException>()));

      expect(adapter.refreshCalls, 1);
      final meRequests = adapter.recordedRequests.where((r) => r.$1 == '/users/me').toList();
      expect(meRequests.length, 2);
      expect(meRequests[0].$2, 'Bearer expired-access');
      expect(meRequests[1].$2, 'Bearer fresh-access');
    });

    test(
        'logout clears profile and trip providers with ZERO unauthenticated /users/me or /trips requests, then new login reloads under new session',
        () async {
      SharedPreferences.setMockInitialValues({
        'access_token': 'access-a',
        'refresh_token': 'refresh-a',
      });

      final adapter = _ControllableAuthAdapter(
        onRequest: (options) async {
          if (options.path == '/auth/login') {
            final body = Map<String, dynamic>.from(options.data as Map);
            expect(body['email'], 'b@test');
            return _jsonBody(200, {
              'success': true,
              'data': {
                'access_token': 'access-b',
                'refresh_token': 'refresh-b',
              },
            });
          }
          final auth = options.headers['Authorization'] as String?;
          if (options.path == '/users/me') {
            if (auth == 'Bearer access-a') {
              return _jsonBody(200, {
                'success': true,
                'data': {'id': 'user-a', 'email': 'a@test'},
              });
            }
            if (auth == 'Bearer access-b') {
              return _jsonBody(200, {
                'success': true,
                'data': {'id': 'user-b', 'email': 'b@test'},
              });
            }
            return _jsonBody(401, {'message': 'Unauthorized /users/me'});
          }
          if (options.path == '/trips') {
            if (auth == 'Bearer access-a') {
              return _jsonBody(200, {
                'success': true,
                'data': {'items': <dynamic>[]},
              });
            }
            if (auth == 'Bearer access-b') {
              return _jsonBody(200, {
                'success': true,
                'data': {'items': <dynamic>[]},
              });
            }
            return _jsonBody(401, {'message': 'Unauthorized /trips'});
          }
          return _jsonBody(200, {'success': true, 'data': {}});
        },
      );

      final container = ProviderContainer(
        overrides: [
          apiClientProvider.overrideWith((ref) {
            final epoch = ref.read(sessionEpochControllerProvider);
            return createApiClient(
              baseUrlOverride: 'http://localhost:3000/api/v1',
              sessionEpoch: epoch,
              onSessionExpired: () {
                ref.read(authSessionExpiredSignalProvider.notifier).state++;
              },
            )..httpClientAdapter = adapter;
          }),
        ],
      );
      addTearDown(container.dispose);

      container.read(routerNotifierProvider);
      await Future<void>.delayed(const Duration(milliseconds: 30));
      expect(container.read(authProvider).status, AuthStatus.authenticated);

      // Hydrate session-scoped providers as User A.
      container.read(profileProvider);
      container.read(tripListProvider);
      await Future<void>.delayed(const Duration(milliseconds: 30));
      expect(container.read(profileProvider).user?.id, 'user-a');

      adapter.recordedRequests.clear();

      // Logout must reset providers cleanly with zero /users/me or /trips fetches.
      await container.read(authProvider.notifier).logout();
      await Future<void>.delayed(const Duration(milliseconds: 30));

      expect(container.read(authProvider).status, AuthStatus.unauthenticated);
      expect(container.read(profileProvider).user, isNull);
      expect(container.read(tripListProvider).trips, isEmpty);
      expect(adapter.recordedRequests, isEmpty);

      // Login as User B: invalidated providers reload under B's access token.
      expect(
        await container.read(authProvider.notifier).login('b@test', 'pw'),
        isTrue,
      );
      await Future<void>.delayed(const Duration(milliseconds: 30));
      expect(container.read(authProvider).status, AuthStatus.authenticated);

      container.read(profileProvider);
      await Future<void>.delayed(const Duration(milliseconds: 30));
      expect(container.read(profileProvider).user?.id, 'user-b');
      expect(
        adapter.recordedRequests.where((r) => r.$1 == '/users/me' && r.$2 == 'Bearer access-b'),
        hasLength(1),
      );
    });
  });
}
