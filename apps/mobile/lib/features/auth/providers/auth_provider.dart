import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/auth_repository.dart';
import '../data/auth_models.dart';
import '../../../core/network/api_client.dart';

/// Authentication states.
enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthState {
  final AuthStatus status;
  final String? errorMessage;

  const AuthState({required this.status, this.errorMessage});

  const AuthState.unknown() : status = AuthStatus.unknown, errorMessage = null;
  const AuthState.authenticated() : status = AuthStatus.authenticated, errorMessage = null;
  const AuthState.unauthenticated({this.errorMessage}) : status = AuthStatus.unauthenticated;
}

/// Single source of truth for authentication.
class AuthNotifier extends StateNotifier<AuthState> {
  final AuthRepository _repo;

  AuthNotifier(this._repo) : super(const AuthState.unknown()) {
    _init();
  }

  Future<void> _init() async {
    final hasToken = await _repo.restoreSession();
    if (hasToken) {
      state = const AuthState.authenticated();
    } else {
      state = const AuthState.unauthenticated();
    }
  }

  Future<bool> login(String email, String password) async {
    try {
      await _repo.login(LoginRequest(email: email, password: password));
      state = const AuthState.authenticated();
      return true;
    } on DioException catch (e) {
      state = AuthState.unauthenticated(errorMessage: _mapError(e));
      return false;
    }
  }

  Future<bool> register(String name, String email, String password) async {
    try {
      await _repo.register(RegisterRequest(name: name, email: email, password: password));
      state = const AuthState.authenticated();
      return true;
    } on DioException catch (e) {
      state = AuthState.unauthenticated(errorMessage: _mapError(e));
      return false;
    }
  }

  Future<void> logout() async {
    await _repo.logout();
    state = const AuthState.unauthenticated();
  }

  /// Map API/network errors to user-friendly Vietnamese messages.
  String _mapError(DioException e) {
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout) {
      return 'Không thể kết nối máy chủ. Vui lòng thử lại.';
    }
    if (e.type == DioExceptionType.connectionError) {
      return 'Không có kết nối mạng.';
    }
    final statusCode = e.response?.statusCode;
    final data = e.response?.data;
    if (statusCode == 401) {
      return 'Email hoặc mật khẩu không đúng.';
    }
    if (statusCode == 400 && data is Map) {
      final msg = data['message'];
      if (msg is String) {
        if (msg.contains('đã được sử dụng') || msg.contains('already')) {
          return 'Email đã được sử dụng.';
        }
        return msg;
      }
    }
    return 'Có lỗi xảy ra. Vui lòng thử lại.';
  }
}

/// Riverpod provider for AuthRepository.
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final dio = ref.read(apiClientProvider);
  return AuthRepository(dio);
});

/// Riverpod provider for auth state — single source of truth.
final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final repo = ref.read(authRepositoryProvider);
  return AuthNotifier(repo);
});
