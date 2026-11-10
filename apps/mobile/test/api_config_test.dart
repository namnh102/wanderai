import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wanderai_mobile/core/constants/app_constants.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';

void main() {
  group('PROD-NET-01: AppConstants.resolveApiBaseUrl & validation', () {
    test('1. Debug mode defaults to http://localhost:3000 when API_BASE_URL is omitted', () {
      final resolved = AppConstants.resolveApiBaseUrl(
        rawUrl: '',
        isReleaseMode: false,
        isProfileMode: false,
      );
      expect(resolved, 'http://localhost:3000');
    });

    test('2. Debug mode accepts Android emulator (10.0.2.2) and LAN IP HTTP URLs and strips trailing slashes', () {
      expect(
        AppConstants.resolveApiBaseUrl(
          rawUrl: 'http://10.0.2.2:3000/',
          isReleaseMode: false,
          isProfileMode: false,
        ),
        'http://10.0.2.2:3000',
      );

      expect(
        AppConstants.resolveApiBaseUrl(
          rawUrl: '  http://192.168.1.42:3000///  ',
          isReleaseMode: false,
          isProfileMode: false,
        ),
        'http://192.168.1.42:3000',
      );
    });

    test('3. Release and profile modes accept valid non-loopback HTTPS URLs', () {
      expect(
        AppConstants.resolveApiBaseUrl(
          rawUrl: 'https://api.gomate.example.com/',
          isReleaseMode: true,
          isProfileMode: false,
        ),
        'https://api.gomate.example.com',
      );

      expect(
        AppConstants.resolveApiBaseUrl(
          rawUrl: 'https://staging-api.gomate.example.com:8443/api/',
          isReleaseMode: false,
          isProfileMode: true,
        ),
        'https://staging-api.gomate.example.com:8443/api',
      );
    });

    test('4. Release and profile modes fail closed with StateError when API_BASE_URL is missing', () {
      expect(
        () => AppConstants.resolveApiBaseUrl(
          rawUrl: '',
          isReleaseMode: true,
          isProfileMode: false,
        ),
        throwsA(isA<StateError>()),
      );

      expect(
        () => AppConstants.resolveApiBaseUrl(
          rawUrl: '   ',
          isReleaseMode: false,
          isProfileMode: true,
        ),
        throwsA(isA<StateError>()),
      );
    });

    test('5. Release and profile modes reject cleartext HTTP and loopback/emulator hosts', () {
      // Cleartext HTTP in release
      expect(
        () => AppConstants.resolveApiBaseUrl(
          rawUrl: 'http://api.gomate.example.com',
          isReleaseMode: true,
          isProfileMode: false,
        ),
        throwsA(isA<FormatException>()),
      );

      // Loopback or emulator hosts even over HTTPS in release/profile
      for (final disallowed in [
        'https://localhost:3000',
        'https://127.0.0.1:3000',
        'https://10.0.2.2:3000',
        'https://0.0.0.0:3000',
      ]) {
        expect(
          () => AppConstants.resolveApiBaseUrl(
            rawUrl: disallowed,
            isReleaseMode: true,
            isProfileMode: false,
          ),
          throwsA(isA<FormatException>()),
          reason: 'Expected $disallowed to be rejected in release mode',
        );
      }
    });

    test('6. Malformed URLs, unsupported schemes, userInfo, queries, and fragments are rejected', () {
      for (final invalid in [
        'not-a-url',
        '/relative/path',
        'ftp://api.gomate.example.com',
        'ws://localhost:3000',
        'http://',
        'https://user:secret@api.gomate.example.com',
        'https://api.gomate.example.com?env=prod',
        'https://api.gomate.example.com#section',
      ]) {
        expect(
          () => AppConstants.validateAndNormalizeApiBaseUrl(invalid),
          throwsA(isA<FormatException>()),
          reason: 'Expected "$invalid" to be rejected',
        );
      }
    });
  });

  group('PROD-NET-01: Dio apiClientProvider & createApiClient contract', () {
    test('7. createApiClient binds resolved baseUrl, timeouts, and Bearer token interceptor', () async {
      TestWidgetsFlutterBinding.ensureInitialized();
      SharedPreferences.setMockInitialValues({'access_token': 'jwt-test-token-123'});

      final dio = createApiClient(
        baseUrlOverride: 'http://10.0.2.2:3000/',
        isReleaseMode: false,
        isProfileMode: false,
      );

      expect(dio.options.baseUrl, 'http://10.0.2.2:3000');
      expect(dio.options.connectTimeout, const Duration(seconds: 15));
      expect(dio.options.receiveTimeout, const Duration(seconds: 15));
      expect(dio.options.headers['Content-Type'], 'application/json');

      RequestOptions? capturedOptions;
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest: (options, handler) {
            capturedOptions = options;
            handler.resolve(
              Response(
                requestOptions: options,
                statusCode: 200,
                data: {'ok': true},
              ),
            );
          },
        ),
      );

      await dio.post('/ai/chat', data: {'message': 'Xin chào'});
      expect(capturedOptions, isNotNull);
      expect(capturedOptions!.uri.toString(), 'http://10.0.2.2:3000/ai/chat');
      expect(capturedOptions!.headers['Authorization'], 'Bearer jwt-test-token-123');
    });

    test('8. apiClientProvider provides a valid Dio instance in default test/debug mode', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final dio = container.read(apiClientProvider);
      expect(dio.options.baseUrl, 'http://localhost:3000');
    });
  });
}
