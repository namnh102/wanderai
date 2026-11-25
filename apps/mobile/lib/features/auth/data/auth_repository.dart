import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'auth_models.dart';

/// Authentication repository — single abstraction for all auth operations.
///
/// Screens/providers call this, NOT Dio directly.
/// Handles token persistence via SharedPreferences.
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

  /// POST /auth/oauth/google
  Future<AuthTokens> loginWithGoogle(String idToken) async {
    final response = await _dio.post(
      '/auth/oauth/google',
      data: {'idToken': idToken},
    );
    final tokens = AuthTokens.fromJson(response.data['data']);
    await _saveTokens(tokens);
    return tokens;
  }

  /// POST /auth/oauth/facebook
  Future<AuthTokens> loginWithFacebook(String accessToken) async {
    final response = await _dio.post(
      '/auth/oauth/facebook',
      data: {'accessToken': accessToken},
    );
    final tokens = AuthTokens.fromJson(response.data['data']);
    await _saveTokens(tokens);
    return tokens;
  }

  /// POST /auth/forgot-password
  Future<ForgotPasswordResult> forgotPassword(String email) async {
    final response = await _dio.post(
      '/auth/forgot-password',
      data: {'email': email},
    );
    final raw = response.data;
    final data = raw is Map && raw['data'] is Map
        ? Map<String, dynamic>.from(raw['data'] as Map)
        : const <String, dynamic>{};
    return ForgotPasswordResult.fromJson(data);
  }

  /// GET /auth/reset-password/validate?token=...
  Future<ResetTokenValidationResult> validateResetToken(String token) async {
    final response = await _dio.get(
      '/auth/reset-password/validate',
      queryParameters: {'token': token},
    );
    final raw = response.data;
    final data = raw is Map && raw['data'] is Map
        ? Map<String, dynamic>.from(raw['data'] as Map)
        : const <String, dynamic>{};
    return ResetTokenValidationResult.fromJson(data);
  }

  /// POST /auth/reset-password
  Future<ResetPasswordResult> resetPassword({
    required String token,
    required String newPassword,
  }) async {
    final response = await _dio.post(
      '/auth/reset-password',
      data: {'token': token, 'newPassword': newPassword},
    );
    final raw = response.data;
    final data = raw is Map && raw['data'] is Map
        ? Map<String, dynamic>.from(raw['data'] as Map)
        : const <String, dynamic>{};
    return ResetPasswordResult.fromJson(data);
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
