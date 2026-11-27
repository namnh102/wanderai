import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../map/data/place_model.dart';
import '../../map/providers/map_provider.dart';
import '../data/youtube_repository.dart';
import '../data/youtube_update_model.dart';

typedef YoutubeClock = DateTime Function();

/// Injectable UTC clock for deterministic latency measurement & SLA checks.
final youtubeClockProvider =
    Provider<YoutubeClock>((ref) => () => DateTime.now().toUtc());

/// Default foreground auto-refresh cycle for PlaceDetailScreen reviews & rating.
/// Active only while PlaceDetailScreen is mounted, visible, and resumed;
/// uses single-flight sequential scheduling so requests never overlap.
const Duration kDefaultPlaceDetailPollInterval = Duration(seconds: 5);

/// Injectable poll interval for PlaceDetailScreen (`null` or `Duration.zero` disables polling).
final placeDetailPollIntervalProvider = Provider<Duration?>((ref) {
  return kDefaultPlaceDetailPollInterval;
});

/// Loads the factual place detail from GET /places/:id, falling back to the
/// offline region cache when offline on network/connection errors.
/// autoDispose: each visit refetches; the Map's own state is untouched.
final placeDetailProvider =
    FutureProvider.autoDispose.family<PlaceModel, String>((ref, id) async {
  try {
    return await ref.watch(placeRepositoryProvider).getPlaceById(id);
  } catch (e) {
    final isNetworkError = e is SocketException ||
        (e is DioException &&
            e.response == null &&
            (e.type == DioExceptionType.connectionError ||
                e.type == DioExceptionType.connectionTimeout ||
                e.type == DioExceptionType.receiveTimeout ||
                e.type == DioExceptionType.sendTimeout ||
                e.type == DioExceptionType.unknown));
    if (isNetworkError) {
      final cached =
          await ref.read(offlineTileStoreProvider).findCachedPlaceById(id);
      if (cached != null) return cached;
    }
    rethrow;
  }
});

/// Loads YouTube social freshness updates (`DYNAMIC_SOCIAL_FRESHNESS_LAYER`)
/// for a POI, falling back to destination city-level updates when needed.
final placeYoutubeUpdatesProvider =
    FutureProvider.autoDispose.family<YoutubeUpdatesEnvelope, String>(
        (ref, placeId) async {
  final repo = ref.watch(youtubeRepositoryProvider);
  final envelope = await repo.getPlaceUpdates(placeId);
  if (envelope.items.isEmpty &&
      envelope.cityFallbackItems.isEmpty &&
      (envelope.destinationSlug?.trim().isNotEmpty ?? false)) {
    try {
      final destEnvelope = await repo.getDestinationUpdates(
        envelope.destinationSlug!.trim(),
        scope: 'CITY',
      );
      final fallback = destEnvelope.cityFallbackItems.isNotEmpty
          ? destEnvelope.cityFallbackItems
          : destEnvelope.items
              .where((item) => item.scope == YoutubeUpdateScope.city)
              .toList();
      if (fallback.isNotEmpty) {
        return envelope.copyWith(
          cityFallbackTotal: destEnvelope.cityFallbackTotal > 0
              ? destEnvelope.cityFallbackTotal
              : fallback.length,
          cityFallbackItems: fallback,
        );
      }
    } catch (_) {
      // Non-fatal: keep primary envelope when optional fallback call fails.
    }
  }
  return envelope;
});

/// Loads city/destination-level YouTube freshness updates directly.
final destinationYoutubeUpdatesProvider =
    FutureProvider.autoDispose.family<YoutubeUpdatesEnvelope, String>(
        (ref, idOrSlug) {
  return ref
      .watch(youtubeRepositoryProvider)
      .getDestinationUpdates(idOrSlug, scope: 'CITY');
});
