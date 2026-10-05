import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/auth/data/auth_repository.dart';
import 'package:wanderai_mobile/features/auth/data/auth_models.dart';
import 'package:wanderai_mobile/features/auth/presentation/login_screen.dart';
import 'package:wanderai_mobile/features/auth/presentation/register_screen.dart';

/// Fake AuthRepository for unit testing without network calls.
class FakeAuthRepository extends AuthRepository {
  bool shouldFail = false;
  bool _authenticated = false;

  FakeAuthRepository() : super(Dio()); // Dio not used in fake

  @override
  Future<AuthTokens> login(LoginRequest request) async {
    if (shouldFail) throw Exception('Login failed');
    _authenticated = true;
    return const AuthTokens(accessToken: 'fake_token', refreshToken: 'fake_refresh');
  }

  @override
  Future<AuthTokens> register(RegisterRequest request) async {
    if (shouldFail) throw Exception('Register failed');
    _authenticated = true;
    return const AuthTokens(accessToken: 'fake_token', refreshToken: 'fake_refresh');
  }

  @override
  Future<void> logout() async {
    _authenticated = false;
  }

  @override
  Future<bool> isAuthenticated() async => _authenticated;

  @override
  Future<bool> restoreSession() async => _authenticated;

  @override
  Future<String?> getAccessToken() async => _authenticated ? 'fake_token' : null;
}

void main() {
  group('LoginScreen', () {
    testWidgets('renders email and password fields', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            authRepositoryProvider.overrideWithValue(FakeAuthRepository()),
          ],
          child: const MaterialApp(home: LoginScreen()),
        ),
      );
      await tester.pump();

      expect(find.byType(TextFormField), findsNWidgets(2));
      expect(find.text('Email'), findsOneWidget);
      expect(find.text('Dang nhap'), findsOneWidget);
    });

    testWidgets('shows validation error for invalid email', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            authRepositoryProvider.overrideWithValue(FakeAuthRepository()),
          ],
          child: const MaterialApp(home: LoginScreen()),
        ),
      );
      await tester.pump();

      // Enter invalid email, empty password
      await tester.enterText(find.byType(TextFormField).first, 'notanemail');
      await tester.enterText(find.byType(TextFormField).last, '');

      // Tap login
      await tester.tap(find.text('Dang nhap'));
      await tester.pump();

      expect(find.text('Email khong hop le'), findsOneWidget);
    });

    testWidgets('shows validation error for short password', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            authRepositoryProvider.overrideWithValue(FakeAuthRepository()),
          ],
          child: const MaterialApp(home: LoginScreen()),
        ),
      );
      await tester.pump();

      await tester.enterText(find.byType(TextFormField).first, 'test@test.com');
      await tester.enterText(find.byType(TextFormField).last, '123');

      await tester.tap(find.text('Dang nhap'));
      await tester.pump();

      expect(find.text('Mat khau it nhat 6 ky tu'), findsOneWidget);
    });
  });

  group('RegisterScreen', () {
    testWidgets('renders all 4 fields', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            authRepositoryProvider.overrideWithValue(FakeAuthRepository()),
          ],
          child: const MaterialApp(home: RegisterScreen()),
        ),
      );
      await tester.pump();

      expect(find.byType(TextFormField), findsNWidgets(4));
      expect(find.text('Dang ky'), findsOneWidget);
    });
  });

  group('AuthState', () {
    test('initial state is unknown', () {
      const state = AuthState.unknown();
      expect(state.status, AuthStatus.unknown);
      expect(state.errorMessage, isNull);
    });

    test('authenticated state', () {
      const state = AuthState.authenticated();
      expect(state.status, AuthStatus.authenticated);
    });

    test('unauthenticated state with error', () {
      const state = AuthState.unauthenticated(errorMessage: 'test error');
      expect(state.status, AuthStatus.unauthenticated);
      expect(state.errorMessage, 'test error');
    });
  });

  group('FakeAuthRepository', () {
    test('login updates authenticated state', () async {
      final repo = FakeAuthRepository();
      expect(await repo.isAuthenticated(), false);

      await repo.login(const LoginRequest(email: 'a@b.c', password: '123456'));
      expect(await repo.isAuthenticated(), true);
    });

    test('logout clears authenticated state', () async {
      final repo = FakeAuthRepository();
      await repo.login(const LoginRequest(email: 'a@b.c', password: '123456'));
      expect(await repo.isAuthenticated(), true);

      await repo.logout();
      expect(await repo.isAuthenticated(), false);
    });

    test('restoreSession returns false when no token', () async {
      final repo = FakeAuthRepository();
      expect(await repo.restoreSession(), false);
    });

    test('restoreSession returns true after login', () async {
      final repo = FakeAuthRepository();
      await repo.login(const LoginRequest(email: 'a@b.c', password: '123456'));
      expect(await repo.restoreSession(), true);
    });
  });
}
