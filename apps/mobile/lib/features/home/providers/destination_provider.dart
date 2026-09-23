import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/destination_repository.dart';
import '../../../core/network/api_client.dart';

final destinationRepositoryProvider = Provider<DestinationRepository>((ref) {
  return DestinationRepository(apiClient: apiClient);
});

final destinationsProvider = FutureProvider<List<Map<String, dynamic>>>((ref) async {
  final repository = ref.read(destinationRepositoryProvider);
  return repository.getDestinations();
});

final searchQueryProvider = StateProvider<String>((ref) => '');
final selectedRegionProvider = StateProvider<String?>((ref) => null);

final filteredDestinationsProvider = Provider<List<Map<String, dynamic>>>((ref) {
  final destinationsAsyncValue = ref.watch(destinationsProvider);
  final searchQuery = ref.watch(searchQueryProvider).toLowerCase();
  final selectedRegion = ref.watch(selectedRegionProvider);

  return destinationsAsyncValue.maybeWhen(
    data: (destinations) {
      return destinations.where((destination) {
        final name = (destination['name'] ?? '').toString().toLowerCase();
        final matchesSearch = name.contains(searchQuery);
        final matchesRegion = selectedRegion == null || destination['region'] == selectedRegion;
        return matchesSearch && matchesRegion;
      }).toList();
    },
    orElse: () => [],
  );
});