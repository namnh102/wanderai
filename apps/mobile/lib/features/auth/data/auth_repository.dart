import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AuthRepository {
  final Dio apiClient;
  
  AuthRepository({required this.apiClient});

  // Gá»i API Ä‘Äƒng nháº­p
  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await apiClient.post('/auth/login', data: {
      'email': email,
      'password': password,
    });
    return response.data;
  }

  // Gá»i API Ä‘Äƒng kÃ½
  Future<Map<String, dynamic>> register(String name, String email, String password) async {
    final response = await apiClient.post('/auth/register', data: {
      'name': name,
      'email': email,
      'password': password,
    });
    return response.data;
  }

  // LÆ°u token
  Future<void> saveTokens(String accessToken, String refreshToken) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', accessToken);
    await prefs.setString('refresh_token', refreshToken);
  }

  // XÃ³a token khi Ä‘Äƒng xuáº¥t
  Future<void> deleteTokens() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
  }
}