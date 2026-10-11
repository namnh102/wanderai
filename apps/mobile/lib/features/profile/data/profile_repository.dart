import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import 'profile_models.dart';

class ProfileRepository {
  final Dio _dio;

  ProfileRepository(this._dio);

  /// Lấy thông tin user hiện tại kèm travel preferences
  Future<UserProfile> getProfile() async {
    final response = await _dio.get('/users/me');
    final data = response.data['data'] as Map<String, dynamic>;
    return UserProfile.fromJson(data);
  }

  /// Cập nhật sở thích du lịch (PUT /users/me/preferences)
  Future<TravelPreferences> updatePreferences(TravelPreferences preferences) async {
    final response = await _dio.put(
      '/users/me/preferences',
      data: preferences.toJson(),
    );
    final data = response.data['data'] as Map<String, dynamic>;
    return TravelPreferences.fromJson(data);
  }
}

final profileRepositoryProvider = Provider<ProfileRepository>((ref) {
  final dio = ref.read(apiClientProvider);
  return ProfileRepository(dio);
});
