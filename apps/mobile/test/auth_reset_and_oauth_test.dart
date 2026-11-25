import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wanderai_mobile/app/app.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';
import 'package:wanderai_mobile/core/network/api_error.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/core/widgets/app_state_banner.dart';
import 'package:wanderai_mobile/features/auth/data/auth_social_port.dart';
import 'package:wanderai_mobile/features/auth/presentation/forgot_password_screen.dart';
import 'package:wanderai_mobile/features/auth/presentation/login_screen.dart';
import 'package:wanderai_mobile/features/auth/presentation/register_screen.dart';
import 'package:wanderai_mobile/features/auth/presentation/reset_password_screen.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/places/presentation/place_detail_screen.dart';

const _clockTowerId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
const _haLongDestId = '4eec2f30-b67d-4221-b754-8fcc7bb1160e';

class _FakeAuthSocialPort implements AuthSocialPort {
  SocialAuthResult googleResult =
      const SocialAuthSuccess('google-id-token-valid');
  SocialAuthResult facebookResult =
      const SocialAuthSuccess('facebook-access-token-valid');
  Future<SocialAuthResult> Function()? onGoogleSignIn;
  int signOutCalls = 0;

  @override
  Future<SocialAuthResult> signInWithGoogle() async =>
      onGoogleSignIn != null ? await onGoogleSignIn!() : googleResult;

  @override
  Future<SocialAuthResult> signInWithFacebook() async => facebookResult;

  @override
  Future<void> signOutAll() async {
    signOutCalls++;
  }
}

class _AuthContractBackendAdapter implements HttpClientAdapter {
  final List<(String method, String path, Map<String, dynamic>? body)> calls =
      [];

  String? overrideGoogleErrorCode;
  int? overrideGoogleStatusCode;
  String? overrideFacebookErrorCode;
  int? overrideFacebookStatusCode;
  bool failNextValidateWithNetwork = false;
  bool failNextLoginWithInvalidCredentials = false;
  bool failNextRegisterWithEmailExists = false;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final method = options.method.toUpperCase();
    final path = options.path;
    final body = options.data is Map
        ? Map<String, dynamic>.from(options.data as Map)
        : null;
    calls.add((method, path, body));

    if (method == 'POST' && path == '/auth/register') {
      if (failNextRegisterWithEmailExists) {
        failNextRegisterWithEmailExists = false;
        return _json(400, {
          'success': false,
          'statusCode': 400,
          'errorCode': 'EMAIL_ALREADY_EXISTS',
          'message': 'Email đã được sử dụng.',
        });
      }
      return _json(201, {
        'success': true,
        'data': {
          'access_token': 'register-access',
          'refresh_token': 'register-refresh',
        },
      });
    }

    if (method == 'POST' && path == '/auth/login') {
      if (failNextLoginWithInvalidCredentials) {
        failNextLoginWithInvalidCredentials = false;
        return _json(401, {
          'success': false,
          'statusCode': 401,
          'errorCode': 'INVALID_CREDENTIALS',
          'message': 'Email hoặc mật khẩu không đúng.',
        });
      }
      return _json(200, {
        'success': true,
        'data': {
          'access_token': 'login-access',
          'refresh_token': 'login-refresh',
        },
      });
    }

    if (method == 'POST' && path == '/auth/forgot-password') {
      return _json(200, {
        'success': true,
        'data': {
          'sent': true,
          'expiresInMinutes': 30,
          'message':
              'Nếu email tồn tại trong hệ thống, chúng tôi đã gửi hướng dẫn đặt lại mật khẩu.',
        },
      });
    }

    if (method == 'GET' && path == '/auth/reset-password/validate') {
      if (failNextValidateWithNetwork) {
        failNextValidateWithNetwork = false;
        throw DioException(
          requestOptions: options,
          type: DioExceptionType.connectionError,
          message: 'Socket closed',
        );
      }
      final token = options.queryParameters['token']?.toString() ?? '';
      if (token == 'valid-tok') {
        return _json(200, {
          'success': true,
          'data': {
            'valid': true,
            'expiresAt': '2026-11-25T10:00:00.000Z',
          },
        });
      }
      if (token == 'expired-tok') {
        return _json(410, {
          'success': false,
          'statusCode': 410,
          'errorCode': 'RESET_TOKEN_EXPIRED',
          'message': 'Liên kết đặt lại mật khẩu đã hết hạn.',
        });
      }
      if (token == 'used-tok') {
        return _json(410, {
          'success': false,
          'statusCode': 410,
          'errorCode': 'RESET_TOKEN_USED',
          'message': 'Liên kết đặt lại mật khẩu đã được sử dụng.',
        });
      }
      return _json(400, {
        'success': false,
        'statusCode': 400,
        'errorCode': 'RESET_TOKEN_INVALID',
        'message': 'Liên kết đặt lại mật khẩu không hợp lệ.',
      });
    }

    if (method == 'POST' && path == '/auth/reset-password') {
      final token = body?['token']?.toString() ?? '';
      if (token == 'valid-tok') {
        return _json(200, {
          'success': true,
          'data': {
            'reset': true,
            'message': 'Đặt lại mật khẩu thành công.',
          },
        });
      }
      return _json(400, {
        'success': false,
        'statusCode': 400,
        'errorCode': 'RESET_TOKEN_INVALID',
        'message': 'Liên kết đặt lại mật khẩu không hợp lệ.',
      });
    }

    if (method == 'POST' && path == '/auth/oauth/google') {
      if (overrideGoogleErrorCode != null) {
        return _json(overrideGoogleStatusCode ?? 400, {
          'success': false,
          'statusCode': overrideGoogleStatusCode ?? 400,
          'errorCode': overrideGoogleErrorCode,
          'message': overrideGoogleErrorCode == 'OAUTH_EMAIL_UNAVAILABLE'
              ? 'Tài khoản Google chưa cung cấp email.'
              : 'Mã xác thực Google không hợp lệ.',
        });
      }
      return _json(200, {
        'success': true,
        'data': {
          'access_token': 'oauth-google-access',
          'refresh_token': 'oauth-google-refresh',
        },
      });
    }

    if (method == 'POST' && path == '/auth/oauth/facebook') {
      if (overrideFacebookErrorCode != null) {
        return _json(overrideFacebookStatusCode ?? 502, {
          'success': false,
          'statusCode': overrideFacebookStatusCode ?? 502,
          'errorCode': overrideFacebookErrorCode,
          'message': 'Không thể xác thực với Facebook lúc này.',
        });
      }
      return _json(200, {
        'success': true,
        'data': {
          'access_token': 'oauth-fb-access',
          'refresh_token': 'oauth-fb-refresh',
        },
      });
    }

    if (method == 'GET' && path == '/places/$_clockTowerId') {
      return _json(200, {
        'success': true,
        'data': {
          'id': _clockTowerId,
          'name': 'Tháp Đồng Hồ',
          'latitude': 20.9516105,
          'longitude': 107.0851999,
          'isVerified': true,
          'category': {'name': 'attraction'},
          'destination': {
            'id': _haLongDestId,
            'name': 'Hạ Long',
            'slug': 'ha-long',
          },
        },
      });
    }

    if (method == 'GET' && path == '/destinations') {
      return _json(200, {
        'success': true,
        'data': {'items': []},
      });
    }

    if (method == 'GET' && path == '/places') {
      return _json(200, {
        'success': true,
        'data': {'items': [], 'total': 0},
      });
    }

    if (method == 'GET' && path == '/places/trending') {
      return _json(200, {
        'success': true,
        'data': {'items': []},
      });
    }

    if (method == 'GET' && path == '/users/me') {
      return _json(200, {
        'success': true,
        'data': {'id': 'u1', 'email': 'u@gomate.vn'},
      });
    }

    return _json(404, {'message': 'Unhandled $method $path'});
  }

  ResponseBody _json(int code, Map<String, dynamic> payload) {
    return ResponseBody.fromString(
      jsonEncode(payload),
      code,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

ProviderContainer _createContainer(
  _AuthContractBackendAdapter backend,
  AuthSocialPort socialPort,
) {
  return ProviderContainer(
    overrides: [
      authSocialPortProvider.overrideWithValue(socialPort),
      apiClientProvider.overrideWith((ref) {
        final epoch = ref.read(sessionEpochControllerProvider);
        return createApiClient(
          baseUrlOverride: 'http://localhost:3000',
          sessionEpoch: epoch,
          onSessionExpired: () {
            ref.read(authSessionExpiredSignalProvider.notifier).state++;
          },
        )..httpClientAdapter = backend;
      }),
    ],
  );
}

Future<void> _pump(WidgetTester tester, [int count = 6]) async {
  for (var i = 0; i < count; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  group('Deep-link normalization & public auth path guard', () {
    test('normalizeAuthDeepLink maps wanderai:// and https reset-password URIs',
        () {
      expect(
        normalizeAuthDeepLink(
          Uri.parse('wanderai://reset-password?token=abc123'),
        ),
        '/reset-password?token=abc123',
      );
      expect(
        normalizeAuthDeepLink(
          Uri.parse('wanderai://app/reset-password?token=xyz789'),
        ),
        '/reset-password?token=xyz789',
      );
      expect(
        normalizeAuthDeepLink(
          Uri.parse('https://app.gomate.vn/reset-password?token=webtok'),
        ),
        '/reset-password?token=webtok',
      );
      expect(
        normalizeAuthDeepLink(
          Uri.parse('wanderai://app/reset-password/?token=trail'),
        ),
        '/reset-password?token=trail',
      );
      expect(
        normalizeAuthDeepLink(Uri.parse('wanderai://unknown-host')),
        isNull,
      );
      expect(
        normalizeAuthDeepLink(
          Uri.parse('wanderai://app/reset-password-evil?token=x'),
        ),
        isNull,
      );
      expect(
        normalizeAuthDeepLink(
          Uri.parse('wanderai://reset-password/extra?token=x'),
        ),
        isNull,
      );
      expect(
        normalizeAuthDeepLink(
          Uri.parse('http://app.gomate.vn/reset-password?token=x'),
        ),
        isNull,
      );
      expect(
        normalizeAuthDeepLink(
          Uri.parse('https://evil.example.com/reset-password?token=x'),
        ),
        isNull,
      );
    });

    test(
        '401 from /auth/oauth/google does not trigger /auth/refresh single-flight',
        () async {
      SharedPreferences.setMockInitialValues({'refresh_token': 'stale-ref'});
      final backend = _AuthContractBackendAdapter()
        ..overrideGoogleStatusCode = 401
        ..overrideGoogleErrorCode = 'OAUTH_TOKEN_INVALID';
      final dio = createApiClient(baseUrlOverride: 'http://localhost:3000')
        ..httpClientAdapter = backend;

      await expectLater(
        () => dio.post('/auth/oauth/google', data: {'idToken': 'bad'}),
        throwsA(isA<DioException>()),
      );

      expect(
        backend.calls.where((c) => c.$2 == '/auth/refresh'),
        isEmpty,
      );
    });

    test('ApiErrorDetails extracts errorCode and network loss flags', () {
      final req = RequestOptions(path: '/auth/reset-password');
      final netErr = DioException(
        requestOptions: req,
        type: DioExceptionType.connectionError,
      );
      expect(ApiErrorDetails.fromDioException(netErr).isNetworkError, isTrue);

      final apiErr = DioException(
        requestOptions: req,
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: req,
          statusCode: 410,
          data: {
            'errorCode': 'RESET_TOKEN_EXPIRED',
            'message': 'Liên kết đặt lại mật khẩu đã hết hạn.',
          },
        ),
      );
      final parsed = ApiErrorDetails.fromDioException(apiErr);
      expect(parsed.statusCode, 410);
      expect(parsed.errorCode, 'RESET_TOKEN_EXPIRED');
      expect(parsed.message, 'Liên kết đặt lại mật khẩu đã hết hạn.');
      expect(parsed.isNetworkError, isFalse);
    });
  });

  group('ForgotPassword & ResetPassword flows', () {
    testWidgets(
        'Happy path: Login -> ForgotPassword -> ResetPassword?token=valid-tok -> Login',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter();
      final socialPort = _FakeAuthSocialPort();
      final container = _createContainer(backend, socialPort);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 6);
      expect(find.byType(LoginScreen), findsOneWidget);

      await tester
          .tap(find.byKey(const Key('login_forgot_password_button')));
      await _pump(tester, 6);
      expect(find.byType(ForgotPasswordScreen), findsOneWidget);

      await tester.enterText(
        find.byKey(const Key('forgot_email_input')),
        'traveler@gomate.vn',
      );
      await tester.tap(find.byKey(const Key('forgot_submit_button')));
      await _pump(tester, 6);

      expect(
        backend.calls.where((c) => c.$2 == '/auth/forgot-password'),
        hasLength(1),
      );
      expect(find.byKey(const Key('forgot_result_banner')), findsOneWidget);
      expect(find.textContaining('Nếu email tồn tại'), findsOneWidget);

      // Navigate via deep-link target `/reset-password?token=valid-tok`
      container.read(appRouterProvider).go('/reset-password?token=valid-tok');
      await _pump(tester, 6);
      expect(find.byType(ResetPasswordScreen), findsOneWidget);
      expect(
        backend.calls.where((c) => c.$2 == '/auth/reset-password/validate'),
        hasLength(1),
      );

      await tester.enterText(
        find.byKey(const Key('reset_password_input')),
        'NewPass123!',
      );
      await tester.enterText(
        find.byKey(const Key('reset_confirm_password_input')),
        'NewPass123!',
      );
      await tester.tap(find.byKey(const Key('reset_submit_button')));
      await _pump(tester, 6);

      expect(
        backend.calls.where((c) => c.$2 == '/auth/reset-password'),
        hasLength(1),
      );
      expect(find.byKey(const Key('reset_status_banner')), findsOneWidget);
      expect(find.byKey(const Key('reset_go_login_button')), findsOneWidget);

      await tester.tap(find.byKey(const Key('reset_go_login_button')));
      await _pump(tester, 6);
      expect(find.byType(LoginScreen), findsOneWidget);
    });

    testWidgets(
        'Expired link (RESET_TOKEN_EXPIRED) shows error banner + CTA to request new link',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter();
      final container = _createContainer(backend, _FakeAuthSocialPort());
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 4);

      container.read(appRouterProvider).go('/reset-password?token=expired-tok');
      await _pump(tester, 6);

      expect(find.byKey(const Key('reset_status_banner')), findsOneWidget);
      expect(find.textContaining('hết hạn'), findsOneWidget);
      expect(find.byKey(const Key('reset_submit_button')), findsNothing);

      await tester.tap(find.byKey(const Key('reset_request_new_button')));
      await _pump(tester, 6);
      expect(find.byType(ForgotPasswordScreen), findsOneWidget);
    });

    testWidgets(
        'Used link (RESET_TOKEN_USED) and invalid link (RESET_TOKEN_INVALID) block password form',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter();
      final container = _createContainer(backend, _FakeAuthSocialPort());
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 4);

      container.read(appRouterProvider).go('/reset-password?token=used-tok');
      await _pump(tester, 6);
      expect(find.byKey(const Key('reset_status_banner')), findsOneWidget);
      expect(find.textContaining('đã được sử dụng'), findsOneWidget);
      expect(find.byKey(const Key('reset_submit_button')), findsNothing);

      container.read(appRouterProvider).go('/reset-password?token=bad-tok');
      await _pump(tester, 6);
      expect(find.byKey(const Key('reset_status_banner')), findsOneWidget);
      expect(find.textContaining('không hợp lệ'), findsOneWidget);
      expect(find.byKey(const Key('reset_submit_button')), findsNothing);
    });
  });

  group('Google & Facebook OAuth flows (Success / Cancelled / Error)', () {
    testWidgets(
        'Google success persists tokens, clears guest mode, and honors redirect to Tháp Đồng Hồ',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter();
      final socialPort = _FakeAuthSocialPort()
        ..googleResult = const SocialAuthSuccess('google-tok-ok');
      final container = _createContainer(backend, socialPort);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 4);

      container.read(guestBrowseModeProvider.notifier).state = true;
      container.read(appRouterProvider).go(
          '/login?redirect=${Uri.encodeComponent('/places/$_clockTowerId')}');
      await _pump(tester, 6);

      await tester.ensureVisible(find.byKey(const Key('login_google_button')));
      await tester.tap(find.byKey(const Key('login_google_button')));
      await _pump(tester, 8);

      expect(
        backend.calls.where((c) => c.$2 == '/auth/oauth/google'),
        hasLength(1),
      );
      expect(container.read(authProvider).status, AuthStatus.authenticated);
      expect(container.read(guestBrowseModeProvider), isFalse);
      expect(find.byType(PlaceDetailScreen), findsOneWidget);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('access_token'), 'oauth-google-access');
    });

    testWidgets(
        'Google cancelled does NOT call backend or render error banner',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter();
      final socialPort = _FakeAuthSocialPort()
        ..googleResult = const SocialAuthCancelled();
      final container = _createContainer(backend, socialPort);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 6);

      await tester.ensureVisible(find.byKey(const Key('login_google_button')));
      await tester.tap(find.byKey(const Key('login_google_button')));
      await _pump(tester, 6);

      expect(
        backend.calls.where((c) => c.$2 == '/auth/oauth/google'),
        isEmpty,
      );
      expect(container.read(authProvider).status, AuthStatus.unauthenticated);
      expect(find.byKey(const Key('login_error_banner')), findsNothing);
    });

    testWidgets(
        'Google provider & backend OAUTH_EMAIL_UNAVAILABLE error shows AppStateBanner',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter()
        ..overrideGoogleStatusCode = 400
        ..overrideGoogleErrorCode = 'OAUTH_EMAIL_UNAVAILABLE';
      final socialPort = _FakeAuthSocialPort();
      final container = _createContainer(backend, socialPort);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 6);

      await tester.ensureVisible(find.byKey(const Key('login_google_button')));
      await tester.tap(find.byKey(const Key('login_google_button')));
      await _pump(tester, 6);

      final bannerFinder = find.byKey(const Key('login_error_banner'));
      expect(bannerFinder, findsOneWidget);
      final banner = tester.widget<AppStateBanner>(bannerFinder);
      expect(banner.tone, AppStateBannerTone.error);
      expect(find.textContaining('email'), findsWidgets);
      expect(container.read(authProvider).status, AuthStatus.unauthenticated);

      // SDK failure without calling backend
      socialPort.googleResult = const SocialAuthFailure(
        'Google SDK bị gián đoạn',
        errorCode: 'OAUTH_PROVIDER_ERROR',
      );
      await tester.tap(find.byKey(const Key('login_google_button')));
      await _pump(tester, 6);
      expect(find.text('Google SDK bị gián đoạn'), findsOneWidget);
    });

    testWidgets('Facebook success, cancelled, and 502 error flows',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter();
      final socialPort = _FakeAuthSocialPort();
      final container = _createContainer(backend, socialPort);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 6);

      // 1. Cancelled
      socialPort.facebookResult = const SocialAuthCancelled();
      await tester.ensureVisible(find.byKey(const Key('login_facebook_button')));
      await tester.tap(find.byKey(const Key('login_facebook_button')));
      await _pump(tester, 6);
      expect(
        backend.calls.where((c) => c.$2 == '/auth/oauth/facebook'),
        isEmpty,
      );
      expect(find.byKey(const Key('login_error_banner')), findsNothing);

      // 2. Backend 502 OAUTH_PROVIDER_ERROR
      socialPort.facebookResult = const SocialAuthSuccess('fb-tok');
      backend.overrideFacebookStatusCode = 502;
      backend.overrideFacebookErrorCode = 'OAUTH_PROVIDER_ERROR';
      await tester.tap(find.byKey(const Key('login_facebook_button')));
      await _pump(tester, 6);
      expect(find.byKey(const Key('login_error_banner')), findsOneWidget);
      expect(find.textContaining('Facebook'), findsWidgets);

      // 3. Success
      backend.overrideFacebookErrorCode = null;
      await tester.tap(find.byKey(const Key('login_facebook_button')));
      await _pump(tester, 6);
      expect(container.read(authProvider).status, AuthStatus.authenticated);
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('access_token'), 'oauth-fb-access');
    });

    testWidgets(
        'ResetPasswordScreen offers explicit retry on transient network error and recovers',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter()
        ..failNextValidateWithNetwork = true;
      final container = _createContainer(backend, _FakeAuthSocialPort());
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 4);

      container.read(appRouterProvider).go('/reset-password?token=valid-tok');
      await _pump(tester, 6);

      final bannerFinder = find.byKey(const Key('reset_status_banner'));
      expect(bannerFinder, findsOneWidget);
      expect(
        tester.widget<AppStateBanner>(bannerFinder).tone,
        AppStateBannerTone.warning,
      );
      expect(
        find.byKey(const Key('reset_retry_validate_button')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('reset_submit_button')), findsNothing);

      await tester.tap(find.byKey(const Key('reset_retry_validate_button')));
      await _pump(tester, 6);

      expect(find.byKey(const Key('reset_submit_button')), findsOneWidget);
      expect(
        find.byKey(const Key('reset_retry_validate_button')),
        findsNothing,
      );
    });

    testWidgets(
        'LoginScreen clears stale inline error banner immediately when Google OAuth starts',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter()
        ..failNextLoginWithInvalidCredentials = true;
      final pendingGoogle = Completer<SocialAuthResult>();
      final socialPort = _FakeAuthSocialPort()
        ..onGoogleSignIn = () => pendingGoogle.future;
      final container = _createContainer(backend, socialPort);
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 6);

      await tester.enterText(
        find.byKey(const Key('login_email_input')),
        'traveler@gomate.vn',
      );
      await tester.enterText(
        find.byKey(const Key('login_password_input')),
        'wrongpass',
      );
      await tester.tap(find.byKey(const Key('login_submit_button')));
      await _pump(tester, 6);

      expect(find.byKey(const Key('login_error_banner')), findsOneWidget);

      await tester.ensureVisible(find.byKey(const Key('login_google_button')));
      await tester.tap(find.byKey(const Key('login_google_button')));
      await _pump(tester, 2);

      // While OAuth SDK is still pending, stale email error must already be gone.
      expect(find.byKey(const Key('login_error_banner')), findsNothing);
      expect(container.read(authProvider).errorMessage, isNull);

      pendingGoogle.complete(const SocialAuthCancelled());
      await _pump(tester, 6);
      expect(find.byKey(const Key('login_error_banner')), findsNothing);
    });

    testWidgets(
        'Cancel login and guest explore clear auth error so returning to /login has no stale error banner',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter()
        ..failNextLoginWithInvalidCredentials = true;
      final container = _createContainer(backend, _FakeAuthSocialPort());
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 4);

      container.read(appRouterProvider).go(
          '/login?redirect=${Uri.encodeComponent('/places/$_clockTowerId')}');
      await _pump(tester, 6);

      await tester.enterText(
        find.byKey(const Key('login_email_input')),
        'traveler@gomate.vn',
      );
      await tester.enterText(
        find.byKey(const Key('login_password_input')),
        'wrongpass',
      );
      await tester.tap(find.byKey(const Key('login_submit_button')));
      await _pump(tester, 6);
      expect(find.byKey(const Key('login_error_banner')), findsOneWidget);

      await tester.ensureVisible(find.byKey(const Key('login_cancel_button')));
      await tester.tap(find.byKey(const Key('login_cancel_button')));
      await _pump(tester, 6);
      expect(find.byType(PlaceDetailScreen), findsOneWidget);
      expect(container.read(authProvider).errorMessage, isNull);

      container.read(appRouterProvider).go('/login');
      await _pump(tester, 6);
      expect(find.byType(LoginScreen), findsOneWidget);
      expect(find.byKey(const Key('login_error_banner')), findsNothing);

      // Now fail login again and tap guest explore button.
      backend.failNextLoginWithInvalidCredentials = true;
      await tester.enterText(
        find.byKey(const Key('login_email_input')),
        'traveler@gomate.vn',
      );
      await tester.enterText(
        find.byKey(const Key('login_password_input')),
        'wrongpass2',
      );
      await tester.tap(find.byKey(const Key('login_submit_button')));
      await _pump(tester, 6);
      expect(find.byKey(const Key('login_error_banner')), findsOneWidget);

      await tester.ensureVisible(
          find.byKey(const Key('login_guest_explore_button')));
      await tester.tap(find.byKey(const Key('login_guest_explore_button')));
      await _pump(tester, 6);
      expect(container.read(authProvider).errorMessage, isNull);

      container.read(appRouterProvider).go('/login');
      await _pump(tester, 6);
      expect(find.byType(LoginScreen), findsOneWidget);
      expect(find.byKey(const Key('login_error_banner')), findsNothing);
    });

    testWidgets(
        'Failed registration + register_cancel_button clears auth error and hides login_error_banner on return',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter()
        ..failNextRegisterWithEmailExists = true;
      final container = _createContainer(backend, _FakeAuthSocialPort());
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 4);

      container.read(appRouterProvider).go(
          '/register?redirect=${Uri.encodeComponent('/places/$_clockTowerId')}');
      await _pump(tester, 6);
      expect(find.byType(RegisterScreen), findsOneWidget);

      await tester.enterText(
        find.byKey(const Key('register_name_input')),
        'Traveler',
      );
      await tester.enterText(
        find.byKey(const Key('register_email_input')),
        'existing@gomate.vn',
      );
      await tester.enterText(
        find.byKey(const Key('register_password_input')),
        'secret123',
      );
      await tester.enterText(
        find.byKey(const Key('register_confirm_password_input')),
        'secret123',
      );
      await tester.ensureVisible(
          find.byKey(const Key('register_submit_button')));
      await tester.tap(find.byKey(const Key('register_submit_button')));
      await _pump(tester, 6);

      expect(find.byKey(const Key('register_error_banner')), findsOneWidget);
      expect(container.read(authProvider).errorMessage, isNotNull);

      await tester.ensureVisible(
          find.byKey(const Key('register_cancel_button')));
      await tester.tap(find.byKey(const Key('register_cancel_button')));
      await _pump(tester, 6);

      expect(find.byType(PlaceDetailScreen), findsOneWidget);
      expect(container.read(authProvider).errorMessage, isNull);

      container.read(appRouterProvider).go('/login');
      await _pump(tester, 6);
      expect(find.byType(LoginScreen), findsOneWidget);
      expect(find.byKey(const Key('login_error_banner')), findsNothing);
    });

    testWidgets(
        'Switching between Login and Register clears auth error so login_error_banner does not leak',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter()
        ..failNextLoginWithInvalidCredentials = true
        ..failNextRegisterWithEmailExists = true;
      final container = _createContainer(backend, _FakeAuthSocialPort());
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 4);

      container.read(appRouterProvider).go('/login');
      await _pump(tester, 6);

      await tester.enterText(
        find.byKey(const Key('login_email_input')),
        'traveler@gomate.vn',
      );
      await tester.enterText(
        find.byKey(const Key('login_password_input')),
        'wrongpass',
      );
      await tester.tap(find.byKey(const Key('login_submit_button')));
      await _pump(tester, 6);
      expect(find.byKey(const Key('login_error_banner')), findsOneWidget);
      expect(container.read(authProvider).errorMessage, isNotNull);

      await tester.ensureVisible(
          find.byKey(const Key('login_go_register_button')));
      await tester.tap(find.byKey(const Key('login_go_register_button')));
      await _pump(tester, 6);

      expect(find.byType(RegisterScreen), findsOneWidget);
      expect(container.read(authProvider).errorMessage, isNull);

      // Fail registration, then return to login via "Đã có tài khoản? Đăng nhập".
      await tester.enterText(
        find.byKey(const Key('register_name_input')),
        'Traveler',
      );
      await tester.enterText(
        find.byKey(const Key('register_email_input')),
        'existing@gomate.vn',
      );
      await tester.enterText(
        find.byKey(const Key('register_password_input')),
        'secret123',
      );
      await tester.enterText(
        find.byKey(const Key('register_confirm_password_input')),
        'secret123',
      );
      await tester.ensureVisible(
          find.byKey(const Key('register_submit_button')));
      await tester.tap(find.byKey(const Key('register_submit_button')));
      await _pump(tester, 6);
      expect(find.byKey(const Key('register_error_banner')), findsOneWidget);
      expect(container.read(authProvider).errorMessage, isNotNull);

      final goLoginFinder = find.text('Đã có tài khoản? Đăng nhập');
      await tester.ensureVisible(goLoginFinder);
      await tester.tap(goLoginFinder);
      await _pump(tester, 6);

      expect(find.byType(LoginScreen), findsOneWidget);
      expect(container.read(authProvider).errorMessage, isNull);
      expect(find.byKey(const Key('login_error_banner')), findsNothing);
    });

    testWidgets(
        'GAP-08: Login -> ForgotPassword -> Back clears auth error and RegisterScreen rejects whitespace-only name',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final backend = _AuthContractBackendAdapter()
        ..failNextLoginWithInvalidCredentials = true;
      final container = _createContainer(backend, _FakeAuthSocialPort());
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: container.read(appRouterProvider),
          ),
        ),
      );
      await _pump(tester, 4);

      container.read(appRouterProvider).go('/login');
      await _pump(tester, 6);

      await tester.enterText(
        find.byKey(const Key('login_email_input')),
        'traveler@gomate.vn',
      );
      await tester.enterText(
        find.byKey(const Key('login_password_input')),
        'wrongpass',
      );
      await tester.tap(find.byKey(const Key('login_submit_button')));
      await _pump(tester, 6);
      expect(find.byKey(const Key('login_error_banner')), findsOneWidget);

      await tester.ensureVisible(
          find.byKey(const Key('login_forgot_password_button')));
      await tester.tap(find.byKey(const Key('login_forgot_password_button')));
      await _pump(tester, 6);
      expect(find.byType(ForgotPasswordScreen), findsOneWidget);

      await tester.ensureVisible(
          find.byKey(const Key('forgot_back_login_button')));
      await tester.tap(find.byKey(const Key('forgot_back_login_button')));
      await _pump(tester, 6);

      expect(find.byType(LoginScreen), findsOneWidget);
      expect(container.read(authProvider).errorMessage, isNull);
      expect(find.byKey(const Key('login_error_banner')), findsNothing);

      // RegisterScreen rejects whitespace-only name before hitting /auth/register
      container.read(appRouterProvider).go('/register');
      await _pump(tester, 6);
      expect(find.byType(RegisterScreen), findsOneWidget);

      await tester.enterText(
        find.byKey(const Key('register_name_input')),
        '   \t ',
      );
      await tester.enterText(
        find.byKey(const Key('register_email_input')),
        'new@gomate.vn',
      );
      await tester.enterText(
        find.byKey(const Key('register_password_input')),
        'secret123',
      );
      await tester.enterText(
        find.byKey(const Key('register_confirm_password_input')),
        'secret123',
      );
      await tester.ensureVisible(
          find.byKey(const Key('register_submit_button')));
      await tester.tap(find.byKey(const Key('register_submit_button')));
      await _pump(tester, 4);

      expect(find.text('Vui lòng nhập tên'), findsOneWidget);
      expect(
        backend.calls.where((c) => c.$2 == '/auth/register'),
        isEmpty,
      );
    });

    test('GAP-09: AuthNotifier.logout awaits signOutAll before completing and survives errors', () async {
      SharedPreferences.setMockInitialValues({'access_token': 'tok-1'});
      final backend = _AuthContractBackendAdapter();
      final signOutGate = Completer<void>();
      var signOutFinished = false;
      var signOutFinishedBeforeNextSignIn = false;

      final socialPort = _RacingSocialPort(
        onSignOutAll: () async {
          await signOutGate.future;
          signOutFinished = true;
        },
        onSignInWithGoogle: () async {
          signOutFinishedBeforeNextSignIn = signOutFinished;
          return const SocialAuthCancelled();
        },
      );

      final container = _createContainer(backend, socialPort);
      addTearDown(container.dispose);

      // Allow _init() to complete
      await Future<void>.delayed(Duration.zero);

      var logoutCompleted = false;
      final logoutFuture = container.read(authProvider.notifier).logout().then((_) {
        logoutCompleted = true;
      });
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(logoutCompleted, isFalse);

      signOutGate.complete();
      await logoutFuture;
      expect(logoutCompleted, isTrue);

      await container.read(authProvider.notifier).signInWithGoogle();
      expect(signOutFinishedBeforeNextSignIn, isTrue);
      expect(container.read(authProvider).status, AuthStatus.unauthenticated);

      // Also survives signOutAll throwing an error
      final throwingPort = _RacingSocialPort(
        onSignOutAll: () async {
          throw StateError('SDK signOut failure');
        },
        onSignInWithGoogle: () async => const SocialAuthCancelled(),
      );
      final container2 = _createContainer(backend, throwingPort);
      addTearDown(container2.dispose);
      await Future<void>.delayed(Duration.zero);
      await container2.read(authProvider.notifier).logout();
      expect(container2.read(authProvider).status, AuthStatus.unauthenticated);
    });
  });
}

class _RacingSocialPort implements AuthSocialPort {
  final Future<void> Function() onSignOutAll;
  final Future<SocialAuthResult> Function() onSignInWithGoogle;

  _RacingSocialPort({
    required this.onSignOutAll,
    required this.onSignInWithGoogle,
  });

  @override
  Future<SocialAuthResult> signInWithGoogle() => onSignInWithGoogle();

  @override
  Future<SocialAuthResult> signInWithFacebook() async =>
      const SocialAuthCancelled();

  @override
  Future<void> signOutAll() => onSignOutAll();
}
