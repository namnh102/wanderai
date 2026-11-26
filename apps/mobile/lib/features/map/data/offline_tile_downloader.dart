import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';
import 'package:dio/dio.dart';
import 'destination_model.dart';
import 'offline_map_models.dart';
import 'offline_tile_store.dart';
import 'place_model.dart';
import 'place_repository.dart';

/// Result summary returned after an offline map region download completes.
class OfflineDownloadResult {
  final OfflineRegionManifest manifest;
  final int downloadedTiles;
  final int skippedTiles;
  final int failedTiles;
  final Map<int, int> httpStatusCounts;
  final bool cancelled;

  const OfflineDownloadResult({
    required this.manifest,
    required this.downloadedTiles,
    required this.skippedTiles,
    required this.failedTiles,
    required this.httpStatusCounts,
    this.cancelled = false,
  });
}

/// Polite, throttled offline tile & POI downloader honoring ADR-006:
/// - Primary: `https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png`
/// - Fallback: `https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png`
/// - Explicit User-Agent (`WanderAI/1.0 (com.wanderai.mobile)`)
/// - Low concurrency (<= 2) with polite delay between requests
/// - Resumes by skipping already cached valid PNG tiles
class OfflineTileDownloader {
  static const primaryUrlTemplate =
      'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png';
  static const fallbackUrlTemplate =
      'https://{s}.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png';
  static const subdomains = ['a', 'b', 'c'];
  static const defaultUserAgent = 'WanderAI/1.0 (com.wanderai.mobile)';

  final OfflineTileStore _store;
  final Dio _tileDio;
  final PlaceRepository? _placeRepository;
  final Duration requestDelay;
  final int maxConcurrency;
  final String userAgent;

  OfflineTileDownloader({
    required OfflineTileStore store,
    required Dio tileDio,
    PlaceRepository? placeRepository,
    this.requestDelay = const Duration(milliseconds: 100),
    int maxConcurrency = 2,
    this.userAgent = defaultUserAgent,
  })  : _store = store,
        _tileDio = tileDio,
        _placeRepository = placeRepository,
        maxConcurrency = math.max(1, math.min(maxConcurrency, 2));

  static String formatTileUrl(
    String template,
    OfflineTileCoord coord,
  ) {
    final s = subdomains[(coord.x + coord.y) % subdomains.length];
    return template
        .replaceAll('{s}', s)
        .replaceAll('{z}', coord.z.toString())
        .replaceAll('{x}', coord.x.toString())
        .replaceAll('{y}', coord.y.toString());
  }

  Future<OfflineDownloadResult> downloadRegion({
    OfflineRegionPreset preset = halongOfflineRegionPreset,
    bool skipExisting = true,
    void Function(OfflineDownloadProgress progress)? onProgress,
    bool Function()? isCancelled,
  }) async {
    final coords = enumerateTilesForBounds(
      preset.bounds,
      preset.minZoom,
      preset.maxZoom,
    );

    final existingManifest = await _store.loadManifest(preset.regionId);
    DestinationModel? destination = existingManifest?.destination;
    var places = existingManifest?.places ?? const <PlaceModel>[];

    final repo = _placeRepository;
    if (repo != null) {
      final allDestinations = await repo.getDestinations();
      final matches = allDestinations
          .where((d) => d.slug == preset.destinationSlug)
          .toList();
      if (matches.isNotEmpty) {
        destination = matches.first;
        final fetchedPlaces = await repo.getAllPlacesForDestination(
          destinationId: destination.id,
        );
        places = fetchedPlaces.where((p) => p.hasCoordinates).toList();
      }
    }

    var completed = 0;
    var downloaded = 0;
    var skipped = 0;
    var failed = 0;
    var totalDownloadedBytes = 0;
    final statusCounts = <int, int>{};

    void emitProgress({bool isCompleted = false, bool cancelled = false}) {
      onProgress?.call(
        OfflineDownloadProgress(
          completedTiles: completed,
          totalTiles: coords.length,
          downloadedBytes: totalDownloadedBytes,
          failedTiles: failed,
          skippedTiles: skipped,
          isCompleted: isCompleted,
          isCancelled: cancelled,
        ),
      );
    }

    emitProgress();

    var nextIndex = 0;
    var cancelled = false;

    Future<void> runWorker() async {
      while (true) {
        if (isCancelled?.call() == true) {
          cancelled = true;
          return;
        }
        if (nextIndex >= coords.length) return;
        final coord = coords[nextIndex++];

        if (skipExisting &&
            await _store.hasValidTile(
              preset.regionId,
              coord.z,
              coord.x,
              coord.y,
            )) {
          final existingBytes = await _store.readTileBytesForRegion(
            preset.regionId,
            coord.z,
            coord.x,
            coord.y,
          );
          totalDownloadedBytes += existingBytes?.length ?? 0;
          skipped++;
          completed++;
          emitProgress();
          continue;
        }

        final outcome = await _fetchTileWithFallback(coord, statusCounts);
        if (outcome != null) {
          await _store.writeTileBytes(
            preset.regionId,
            coord.z,
            coord.x,
            coord.y,
            outcome,
          );
          totalDownloadedBytes += outcome.length;
          downloaded++;
        } else {
          failed++;
        }
        completed++;
        emitProgress();

        if (requestDelay > Duration.zero && nextIndex < coords.length) {
          await Future<void>.delayed(requestDelay);
        }
      }
    }

    final workerCount = math.min(maxConcurrency, coords.length);
    if (workerCount > 0) {
      await Future.wait(List.generate(workerCount, (_) => runWorker()));
    }

    final measured = await _store.measureRegionTiles(preset.regionId);
    final manifest = OfflineRegionManifest(
      regionId: preset.regionId,
      destinationSlug: preset.destinationSlug,
      name: preset.name,
      bbox: preset.bounds,
      minZoom: preset.minZoom,
      maxZoom: preset.maxZoom,
      recommendedInitialZoom: preset.recommendedInitialZoom,
      tileCount: measured.tileCount,
      expectedTileCount: coords.length,
      downloadedBytes: measured.totalBytes,
      downloadedAt: DateTime.now().toUtc(),
      sourceTemplate: primaryUrlTemplate,
      fallbackTemplate: fallbackUrlTemplate,
      destination: destination,
      places: places,
    );

    if (measured.tileCount > 0 || places.isNotEmpty || destination != null) {
      await _store.saveManifest(manifest);
    }

    emitProgress(isCompleted: !cancelled, cancelled: cancelled);

    return OfflineDownloadResult(
      manifest: manifest,
      downloadedTiles: downloaded,
      skippedTiles: skipped,
      failedTiles: failed,
      httpStatusCounts: Map<int, int>.unmodifiable(statusCounts),
      cancelled: cancelled,
    );
  }

  Future<Uint8List?> _fetchTileWithFallback(
    OfflineTileCoord coord,
    Map<int, int> statusCounts,
  ) async {
    final primaryUrl = formatTileUrl(primaryUrlTemplate, coord);
    final primaryBytes = await _tryFetchPng(primaryUrl, statusCounts);
    if (primaryBytes != null) return primaryBytes;

    if (requestDelay > Duration.zero) {
      await Future<void>.delayed(requestDelay);
    }

    final fallbackUrl = formatTileUrl(fallbackUrlTemplate, coord);
    return _tryFetchPng(fallbackUrl, statusCounts);
  }

  Future<Uint8List?> _tryFetchPng(
    String url,
    Map<int, int> statusCounts,
  ) async {
    try {
      final response = await _tileDio.get<List<int>>(
        url,
        options: Options(
          responseType: ResponseType.bytes,
          headers: {'User-Agent': userAgent},
        ),
      );
      final code = response.statusCode ?? 0;
      statusCounts[code] = (statusCounts[code] ?? 0) + 1;
      if (code != 200 || response.data == null) return null;
      final bytes = Uint8List.fromList(response.data!);
      if (!OfflineTileStore.isValidPng(bytes)) return null;
      return bytes;
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      if (code != null) {
        statusCounts[code] = (statusCounts[code] ?? 0) + 1;
      }
      return null;
    } catch (_) {
      return null;
    }
  }
}
