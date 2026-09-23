import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dio/dio.dart';
import '../data/auth_repository.dart';
import '../../../core/network/api_client.dart';

enum AuthStatus { initial, authenticated, unauthenticated }

class AuthState {
  final AuthStatus status;
  final bool isLoading;
  final String? error;
  final String? email; // Email user đang đăng nhập

  const AuthState({
    this.status = AuthStatus.initial,
    this.isLoading = false,
    this.error,
    this.email,
  });

  AuthState copyWith({AuthStatus? status, bool? isLoading, String? error, String? email}) {
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

  // Kiá»ƒm tra tráº¡ng thÃ¡i Ä‘Äƒng nháº­p
  Future<void> checkAuth() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    if (token != null) {
      state = state.copyWith(status: AuthStatus.authenticated);
    } else {
      state = state.copyWith(status: AuthStatus.unauthenticated);
    }
  }

  // Xá»­ lÃ½ Ä‘Äƒng nháº­p
  Future<bool> login(String email, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final data = await _repo.login(email, password);
      final tokens = data['data'];
      await _repo.saveTokens(tokens['access_token'], tokens['refresh_token']);
      state = state.copyWith(status: AuthStatus.authenticated, isLoading: false, email: email);
      return true;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: _getFriendlyError(e),
      );
      return false;
    }
  }

  // Xá»­ lÃ½ Ä‘Äƒng kÃ½
  Future<bool> register(String name, String email, String password) async {
    state = state.copyWith(isLoading: true, error: null);
    try {
      final data = await _repo.register(name, email, password);
      final tokens = data['data'];
      await _repo.saveTokens(tokens['access_token'], tokens['refresh_token']);
      state = state.copyWith(status: AuthStatus.authenticated, isLoading: false, email: email);
      return true;
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: _getFriendlyError(e),
      );
      return false;
    }
  }

  // Xá»­ lÃ½ Ä‘Äƒng xuáº¥t
  Future<void> logout() async {
    await _repo.deleteTokens();
    state = state.copyWith(status: AuthStatus.unauthenticated);
  }

  // Chuyá»ƒn Ä‘á»•i lá»—i thÃ nh thÃ´ng bÃ¡o dá»… hiá»ƒu
  String _getFriendlyError(dynamic error) {
    if (error is DioException) {
      if (error.response?.statusCode == 401) {
        return 'Email hoáº·c máº­t kháº©u khÃ´ng Ä‘Ãºng.';
      }
      if (error.response?.statusCode == 409) {
        return 'Email Ä‘Ã£ Ä‘Æ°á»£c sá»­ dá»¥ng.';
      }
      return 'Lá»—i káº¿t ná»‘i. Vui lÃ²ng thá»­ láº¡i sau.';
    }
    return 'ÄÃ£ xáº£y ra lá»—i khÃ´ng xÃ¡c Ä‘á»‹nh.';
  }
}

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(apiClient: apiClient);
});

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref.read(authRepositoryProvider));
});