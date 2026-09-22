import '../../../core/network/api_client.dart';
import '../../../core/network/api_endpoints.dart';
import 'destination_model.dart';

class DestinationRepository {
  Future<List<Destination>> getDestinations({int page = 1, int limit = 20, String? search, String? region}) async {
    try {
      final query = <String, dynamic>{'page': page, 'limit': limit};
      if (search != null) query['search'] = search;
      if (region != null && region != 'Tất cả') query['region'] = region;
      
      final res = await apiClient.get(ApiEndpoints.destinations, queryParameters: query);
      return (res.data['items'] as List).map((e) => Destination.fromJson(e)).toList();
    } catch (e) {
      return []; // fallback
    }
  }

  Future<List<Destination>> getPopular() async {
    try {
      final res = await apiClient.get(ApiEndpoints.destinations, queryParameters: {'isPopular': true});
      return (res.data['items'] as List).map((e) => Destination.fromJson(e)).toList();
    } catch (e) {
      return [];
    }
  }
}