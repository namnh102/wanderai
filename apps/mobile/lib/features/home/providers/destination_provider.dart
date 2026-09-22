import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../data/destination_repository.dart';
import '../data/destination_model.dart';

final destinationRepositoryProvider = Provider((ref) => DestinationRepository());

final popularDestinationsProvider = FutureProvider<List<Destination>>((ref) {
  return ref.read(destinationRepositoryProvider).getPopular();
});

final searchProvider = StateProvider<String>((ref) => '');
final regionFilterProvider = StateProvider<String?>((ref) => 'Tất cả');

final filteredDestinationsProvider = FutureProvider<List<Destination>>((ref) {
  final search = ref.watch(searchProvider);
  final region = ref.watch(regionFilterProvider);
  return ref.read(destinationRepositoryProvider).getDestinations(
    search: search.isNotEmpty ? search : null,
    region: region,
  );
});