import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'auth_models.dart';

/// Authentication repository — single abstraction for all auth operations.
///
/// Screens/providers call this, NOT Dio directly.
/// Handles token persistence via SharedPreferences.
///
/// LIMITATION: SharedPreferences stores tokens in plaintext on device.
/// Acceptable for thesis MVP. For production, use flutter_secure_storage.
class AuthRepository {
  final Dio _dio;

  static const _accessTokenKey = 'access_token';
  static const _refreshTokenKey = 'refresh_token';

  AuthRepository(this._dio);

  /// POST /auth/login
  Future<AuthTokens> login(LoginRequest request) async {
    final response = await _dio.post('/auth/login', data: request.toJson());
    final tokens = AuthTokens.fromJson(response.data['data']);
    await _saveTokens(tokens);
    return tokens;
  }

  /// POST /auth/register
  Future<AuthTokens> register(RegisterRequest request) async {
    final response = await _dio.post('/auth/register', data: request.toJson());
    final tokens = AuthTokens.fromJson(response.data['data']);
    await _saveTokens(tokens);
    return tokens;
  }

  /// Remove stored tokens.
  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_accessTokenKey);
    await prefs.remove(_refreshTokenKey);
  }

  /// Check if a stored access token exists.
  Future<bool> isAuthenticated() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(_accessTokenKey);
    return token != null && token.isNotEmpty;
  }

  /// Restore session — returns true if a stored token exists.
  Future<bool> restoreSession() async {
    return isAuthenticated();
  }

  /// Read the stored access token (for API client interceptor).
  Future<String?> getAccessToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_accessTokenKey);
  }

  Future<void> _saveTokens(AuthTokens tokens) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_accessTokenKey, tokens.accessToken);
    await prefs.setString(_refreshTokenKey, tokens.refreshToken);
  }
}
