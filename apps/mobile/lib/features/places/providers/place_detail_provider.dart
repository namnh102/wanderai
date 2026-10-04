import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../map/data/place_model.dart';
import '../../map/providers/map_provider.dart';

/// Loads the factual place detail from GET /places/:id.
/// autoDispose: each visit refetches; the Map's own state is untouched.
final placeDetailProvider =
    FutureProvider.autoDispose.family<PlaceModel, String>((ref, id) {
  return ref.watch(placeRepositoryProvider).getPlaceById(id);
});
