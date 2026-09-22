import 'package:dio/dio.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';

class AuthRepository {
  final ApiClient apiClient;

  AuthRepository(this.apiClient);

  Future<void> login(String email, String password) async {
    await apiClient.dio.post(ApiEndpoints.login, data: {
      'email': email,
      'password': password,
    });
  }

  Future<void> register(String name, String email, String password) async {
    await apiClient.dio.post(ApiEndpoints.register, data: {
      'name': name,
      'email': email,
      'password': password,
    });
  }

  Future<void> refreshToken() async {
    // TODO: implement logic
  }
}
