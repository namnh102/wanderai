import 'package:shared_preferences/shared_preferences.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';

class AuthRepository {
  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await apiClient.post(ApiEndpoints.login, data: {
      'email': email,
      'password': password,
    });
    return response.data;
  }

  Future<void> register(String name, String email, String password) async {
    await apiClient.post(ApiEndpoints.register, data: {
      'name': name,
      'email': email,
      'password': password,
    });
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