import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AuthRepository {
  final Dio apiClient;

  AuthRepository({required this.apiClient});

  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await apiClient.post('/auth/login', data: {
      'email': email,
      'password': password,
    });
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> register(
      String name, String email, String password) async {
    final response = await apiClient.post('/auth/register', data: {
      'displayName': name,
      'email': email,
      'password': password,
    });
    return response.data as Map<String, dynamic>;
  }

  Future<void> saveTokens(String accessToken, String refreshToken) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', accessToken);
    await prefs.setString('refresh_token', refreshToken);
  }

  Future<void> deleteTokens() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
  }
}