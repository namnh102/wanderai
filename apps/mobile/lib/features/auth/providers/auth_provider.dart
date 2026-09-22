import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../data/auth_repository.dart';

enum AuthStateStatus { initial, loading, authenticated, unauthenticated, error }

class AuthState {
  final AuthStateStatus status;
  final String? errorMessage;
  final Map<String, dynamic>? user;

  AuthState({required this.status, this.errorMessage, this.user});

  factory AuthState.initial() => AuthState(status: AuthStateStatus.initial);
  factory AuthState.loading() => AuthState(status: AuthStateStatus.loading);
  factory AuthState.authenticated(Map<String, dynamic> user) => AuthState(status: AuthStateStatus.authenticated, user: user);
  factory AuthState.unauthenticated() => AuthState(status: AuthStateStatus.unauthenticated);
  factory AuthState.error(String message) => AuthState(status: AuthStateStatus.error, errorMessage: message);
}

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRepository _repo;

  AuthNotifier(this._repo) : super(AuthState.initial()) {
    checkAuth();
  }

  Future<void> checkAuth() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    if (token != null) {
      state = AuthState.authenticated({'id': '1', 'name': 'User'}); // Mock user
    } else {
      state = AuthState.unauthenticated();
    }
  }

  Future<void> login(String email, String password) async {
    try {
      state = AuthState.loading();
      final data = await _repo.login(email, password);
      await _repo.saveTokens(data['access_token'], data['refresh_token']);
      state = AuthState.authenticated({'email': email});
    } catch (e) {
      state = AuthState.error(e.toString());
    }
  }

  Future<void> register(String name, String email, String password) async {
    try {
      state = AuthState.loading();
      await _repo.register(name, email, password);
      state = AuthState.unauthenticated(); // Require login after
    } catch (e) {
      state = AuthState.error(e.toString());
    }
  }

  Future<void> logout() async {
    await _repo.deleteTokens();
    state = AuthState.unauthenticated();
  }
}

final authRepositoryProvider = Provider((ref) => AuthRepository());
final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.read(authRepositoryProvider));
});