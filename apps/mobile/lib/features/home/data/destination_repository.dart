import 'package:dio/dio.dart';

class DestinationRepository {
  final Dio apiClient;
  
  DestinationRepository({required this.apiClient});

  // Láº¥y danh sÃ¡ch Ä‘á»‹a Ä‘iá»ƒm
  Future<List<Map<String, dynamic>>> getDestinations({
    int page = 1,
    int limit = 50,
    String? search,
    String? region,
  }) async {
    final response = await apiClient.get('/destinations', queryParameters: {
      'page': page,
      'limit': limit,
      if (search != null && search.isNotEmpty) 'search': search,
      if (region != null) 'region': region,
    });
    final data = response.data;
    if (data['data'] != null && data['data']['items'] != null) {
      return List<Map<String, dynamic>>.from(data['data']['items']);
    }
    return [];
  }
}