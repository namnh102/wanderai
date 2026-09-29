import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import '../data/auth_repository.dart';
import '../../../core/network/api_client.dart';

enum AuthStatus { initial, authenticated, unauthenticated }

class AuthState {
  final AuthStatus status;
  final bool isLoading;
  final String? error;
  final String? email;

  const AuthState({
    this.status = AuthStatus.initial,
    this.isLoading = false,
    this.error,
    this.email,
  });

  AuthState copyWith({
    AuthStatus? status,
    bool? isLoading,
    String? error,
    String? email,
  }) {
    return AuthState(
      status: status ?? this.status,
      isLoading: isLoading ?? this.isLoading,
      error: error,
      email: email ?? this.email,
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRepository _repo;

  AuthNotifier(this._repo) : super(const AuthState()) {
    checkAuth();
  }

  Future<void> checkAuth() async {
    // Khi app khoi dong, kiem tra token trong SharedPreferences
    // API client tu dong them token vao header, neu khong co se bi 401
    try {
      final result = await apiClient.get('/users/me');
      if (result.statusCode == 200) {
        final email = result.data['data']?['email'] as String? ?? '';
        state = state.copyWith(
          status: AuthStatus.authenticated,
          email: email,
        );
        return;
      }
    } catch (_) {}
    state = state.copyWith(status: AuthStatus.unauthenticated);
  }

  Future<bool> login(String email, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final data = await _repo.login(email, password);
      // Response: {success: true, data: {access_token, refresh_token}}
      final tokenData = data['data'] as Map<String, dynamic>?;
      if (tokenData == null) {
        state = state.copyWith(
          isLoading: false,
          error: 'Loi dang nhap. Vui long thu lai.',
        );
        return false;
      }
      await _repo.saveTokens(
        tokenData['access_token'] as String,
        tokenData['refresh_token'] as String,
      );
      state = state.copyWith(
        status: AuthStatus.authenticated,
        isLoading: false,
        email: email,
      );
      return true;
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: _getError(e),
      );
      return false;
    } catch (_) {
      state = state.copyWith(
        isLoading: false,
        error: 'Loi ket noi. Vui long thu lai.',
      );
      return false;
    }
  }

  Future<bool> register(String name, String email, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final data = await _repo.register(name, email, password);
      final tokenData = data['data'] as Map<String, dynamic>?;
      if (tokenData == null) {
        state = state.copyWith(
          isLoading: false,
          error: 'Loi dang ky. Vui long thu lai.',
        );
        return false;
      }
      await _repo.saveTokens(
        tokenData['access_token'] as String,
        tokenData['refresh_token'] as String,
      );
      state = state.copyWith(
        status: AuthStatus.authenticated,
        isLoading: false,
        email: email,
      );
      return true;
    } on DioException catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: _getError(e),
      );
      return false;
    } catch (_) {
      state = state.copyWith(
        isLoading: false,
        error: 'Loi ket noi. Vui long thu lai.',
      );
      return false;
    }
  }

  Future<void> logout() async {
    await _repo.deleteTokens();
    state = const AuthState(status: AuthStatus.unauthenticated);
  }

  String _getError(DioException e) {
    final status = e.response?.statusCode;
    final msg = e.response?.data?['message'];
    if (status == 401) return 'Email hoac mat khau khong dung.';
    if (status == 409) return 'Email nay da duoc su dung.';
    if (status == 400 && msg is String) return msg;
    if (status == 400 && msg is List) return (msg as List).first.toString();
    return 'Loi ket noi. Vui long thu lai.';
  }
}

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(apiClient: apiClient);
});

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.read(authRepositoryProvider));
});