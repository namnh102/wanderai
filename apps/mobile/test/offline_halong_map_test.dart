import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/core/widgets/app_state_banner.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/map/data/cached_offline_tile_provider.dart';
import 'package:wanderai_mobile/features/map/data/destination_model.dart';
import 'package:wanderai_mobile/features/map/data/offline_map_models.dart';
import 'package:wanderai_mobile/features/map/data/offline_tile_downloader.dart';
import 'package:wanderai_mobile/features/map/data/offline_tile_store.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/map/data/place_repository.dart';
import 'package:wanderai_mobile/features/map/presentation/map_screen.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/map_category_bar.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/map_radius_selector.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/offline_map_sheet.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/place_preview_sheet.dart';
import 'package:wanderai_mobile/features/map/providers/map_provider.dart';
import 'package:wanderai_mobile/features/places/providers/place_detail_provider.dart';

/// Valid 1x1 transparent PNG (67 bytes).
final Uint8List _valid1x1Png = Uint8List.fromList(const [
  0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
  0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
  0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
  0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
  0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,
  0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
  0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
  0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
  0x42, 0x60, 0x82,
]);

DestinationModel _halongDest() => const DestinationModel(
      id: 'dest-hl-uuid',
      slug: 'ha-long',
      name: 'Hạ Long',
      latitude: 20.9101,
      longitude: 107.1839,
    );

PlaceModel _thapDongHo() => const PlaceModel(
      id: halongThapDongHoId,
      name: 'Tháp Đồng Hồ',
      nameEn: 'Ha Long Clock Tower',
      description: 'Biểu tượng trung tâm Hòn Gai, Hạ Long.',
      address: 'Ngã tư Loong Toòng, Hạ Long, Quảng Ninh',
      latitude: 20.9516105,
      longitude: 107.0851999,
      categoryName: 'attraction',
      destinationId: 'dest-hl-uuid',
      destinationName: 'Hạ Long',
      isVerified: true,
      provenanceCount: 1,
      source: PlaceSourceInfo(
        name: 'OpenStreetMap',
        sourceId: 'way/674228542',
        canonicalUrl: 'https://www.openstreetmap.org/way/674228542',
        license: 'ODbL 1.0',
        attribution: '© OpenStreetMap contributors',
      ),
    );

PlaceModel _baoTangQuangNinh() => const PlaceModel(
      id: halongBaoTangQuangNinhId,
      name: 'Bảo tàng Quảng Ninh',
      nameEn: 'Quảng Ninh Museum',
      latitude: 20.9486771,
      longitude: 107.0975562,
      categoryName: 'museum',
      destinationId: 'dest-hl-uuid',
      destinationName: 'Hạ Long',
      isVerified: true,
      provenanceCount: 2,
    );

class _FakeLocationService extends LocationService {
  @override
  Future<LocationPermissionState> checkPermission() async =>
      LocationPermissionState.denied;

  @override
  Future<LocationPermissionState> requestPermission() async =>
      LocationPermissionState.denied;

  @override
  Future<bool> isServiceEnabled() async => false;

  @override
  Future<LocationFix> currentFix() async => LocationFix(
        position: const LatLng(20.950, 107.0915),
        accuracyMeters: 15.0,
        timestamp: DateTime.utc(2026, 11, 25),
      );
}

class _FakeOnlinePlaceRepo implements PlaceRepository {
  @override
  Future<List<DestinationModel>> getDestinations({int limit = 50}) async => [
        const DestinationModel(
          id: 'dest-hn',
          slug: 'ha-noi',
          name: 'Hà Nội',
          latitude: 21.0285,
          longitude: 105.8542,
        ),
        const DestinationModel(
          id: 'dest-dn',
          slug: 'da-nang',
          name: 'Đà Nẵng',
          latitude: 16.0544,
          longitude: 108.2022,
        ),
        _halongDest(),
      ];

  @override
  Future<List<PlaceModel>> getPlaces({
    int page = 1,
    int limit = 50,
    String? search,
    String? category,
    String? destinationId,
    bool verifiedOnly = true,
  }) async {
    if (destinationId == 'dest-hl-uuid') {
      return [_thapDongHo(), _baoTangQuangNinh()];
    }
    return const [];
  }

  @override
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10,
    int limit = 50,
    bool verifiedOnly = true,
  }) async =>
      const [];

  @override
  Future<PlaceModel> getPlaceById(String id) async {
    if (id == halongThapDongHoId) return _thapDongHo();
    if (id == halongBaoTangQuangNinhId) return _baoTangQuangNinh();
    throw DioException(
      requestOptions: RequestOptions(path: '/places/$id'),
      type: DioExceptionType.connectionError,
    );
  }
}

class _OfflineFailingPlaceRepo implements PlaceRepository {
  DioException _err(String path) => DioException(
        requestOptions: RequestOptions(path: path),
        type: DioExceptionType.connectionError,
        message: 'Network unreachable (offline test)',
      );

  @override
  Future<List<DestinationModel>> getDestinations({int limit = 50}) async =>
      throw _err('/destinations');

  @override
  Future<List<PlaceModel>> getPlaces({
    int page = 1,
    int limit = 50,
    String? search,
    String? category,
    String? destinationId,
    bool verifiedOnly = true,
  }) async =>
      throw _err('/places');

  @override
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10,
    int limit = 50,
    bool verifiedOnly = true,
  }) async =>
      throw _err('/places/nearby');

  @override
  Future<PlaceModel> getPlaceById(String id) async =>
      throw _err('/places/$id');
}

class _TileRequestRecord {
  final Uri uri;
  final Map<String, dynamic> headers;
  _TileRequestRecord(this.uri, this.headers);
}

class _MockTileHttpAdapter implements HttpClientAdapter {
  final List<_TileRequestRecord> requests = [];
  final bool Function(Uri uri)? failPrimaryCondition;
  final bool Function(Uri uri)? html200Condition;
  final Duration? delay;
  bool failAll;

  _MockTileHttpAdapter({
    this.failPrimaryCondition,
    this.html200Condition,
    this.delay,
    this.failAll = false,
  });

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<List<int>>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(_TileRequestRecord(options.uri, Map.of(options.headers)));
    if (delay != null) {
      await Future<void>.delayed(delay!);
    }
    if (failAll) {
      throw DioException(
        requestOptions: options,
        type: DioExceptionType.connectionError,
      );
    }
    if (html200Condition != null && html200Condition!(options.uri)) {
      return ResponseBody.fromString(
        '<html><body>Rate limited</body></html>',
        200,
        headers: {
          Headers.contentTypeHeader: ['text/html'],
        },
      );
    }
    if (failPrimaryCondition != null && failPrimaryCondition!(options.uri)) {
      return ResponseBody.fromString('Service Unavailable', 503);
    }
    return ResponseBody.fromBytes(
      _valid1x1Png,
      200,
      headers: {
        Headers.contentTypeHeader: ['image/png'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Future<OfflineTileStore> _createTempStore() async {
  final dir = await Directory.systemTemp.createTemp('w09c_halong_test_');
  addTearDown(() {
    try {
      if (dir.existsSync()) {
        dir.deleteSync(recursive: true);
      }
    } catch (_) {
      // Ignore transient Windows file lock during widget test teardown.
    }
  });
  return OfflineTileStore(baseDirProvider: () async => dir);
}

Future<OfflineRegionManifest> _seedFullHalongCache(
  OfflineTileStore store,
) async {
  final coords = enumerateTilesForBounds(
    halongOfflineRegionPreset.bounds,
    halongOfflineRegionPreset.minZoom,
    halongOfflineRegionPreset.maxZoom,
  );
  for (final c in coords) {
    await store.writeTileBytes(
      halongOfflineRegionPreset.regionId,
      c.z,
      c.x,
      c.y,
      _valid1x1Png,
    );
  }
  final measured = await store.measureRegionTiles(
    halongOfflineRegionPreset.regionId,
  );
  final manifest = OfflineRegionManifest(
    regionId: halongOfflineRegionPreset.regionId,
    destinationSlug: halongOfflineRegionPreset.destinationSlug,
    name: halongOfflineRegionPreset.name,
    bbox: halongOfflineRegionPreset.bounds,
    minZoom: halongOfflineRegionPreset.minZoom,
    maxZoom: halongOfflineRegionPreset.maxZoom,
    recommendedInitialZoom: halongOfflineRegionPreset.recommendedInitialZoom,
    tileCount: measured.tileCount,
    expectedTileCount: coords.length,
    downloadedBytes: measured.totalBytes,
    downloadedAt: DateTime.utc(2026, 11, 25, 14, 0, 0),
    sourceTemplate: OfflineTileDownloader.primaryUrlTemplate,
    fallbackTemplate: OfflineTileDownloader.fallbackUrlTemplate,
    destination: _halongDest(),
    places: [_thapDongHo(), _baoTangQuangNinh()],
  );
  await store.saveManifest(manifest);
  return manifest;
}

void main() {
  group('W09-C Halong bbox, POI inclusion & slippy-tile math', () {
    test('Halong preset encloses Tháp Đồng Hồ & Bảo tàng Quảng Ninh', () {
      final bounds = halongOfflineRegionPreset.bounds;
      expect(
        bounds.contains(const LatLng(20.9516105, 107.0851999)),
        isTrue,
        reason: 'Tháp Đồng Hồ must be inside downloaded bbox',
      );
      expect(
        bounds.contains(const LatLng(20.9486771, 107.0975562)),
        isTrue,
        reason: 'Bảo tàng Quảng Ninh must be inside downloaded bbox',
      );
      expect(
        bounds.contains(const LatLng(21.0285, 105.8542)),
        isFalse,
        reason: 'Hanoi must be outside Halong bbox',
      );
      expect(bounds.center.latitude, closeTo(20.950, 1e-6));
      expect(bounds.center.longitude, closeTo(107.0915, 1e-6));
    });

    test('enumerateTilesForBounds yields exact 112 unique tiles for z=12..17', () {
      final bounds = halongOfflineRegionPreset.bounds;
      final all = enumerateTilesForBounds(bounds, 12, 17);
      expect(all.length, 112);
      expect(all.toSet().length, 112);

      final byZoom = <int, int>{};
      for (final t in all) {
        byZoom[t.z] = (byZoom[t.z] ?? 0) + 1;
      }
      expect(byZoom, {12: 1, 13: 2, 14: 2, 15: 6, 16: 24, 17: 77});
    });
  });

  group('W09-C Model toJson/fromJson round-trips', () {
    test('DestinationModel round-trips 100%', () {
      final d = _halongDest();
      final decoded = DestinationModel.fromJson(
        jsonDecode(jsonEncode(d.toJson())) as Map<String, dynamic>,
      );
      expect(decoded.id, d.id);
      expect(decoded.slug, d.slug);
      expect(decoded.name, d.name);
      expect(decoded.latitude, d.latitude);
      expect(decoded.longitude, d.longitude);
    });

    test('PlaceModel with source, enrichmentMeta & reviews round-trips 100%', () {
      final original = PlaceModel(
        id: halongThapDongHoId,
        name: 'Tháp Đồng Hồ',
        nameEn: 'Clock Tower',
        description: 'Công trình biểu tượng tại Hòn Gai.',
        address: 'Ngã tư Loong Toòng, Hạ Long',
        latitude: 20.9516105,
        longitude: 107.0851999,
        rating: 4.6,
        reviewCount: 2,
        coverImage: 'https://example.org/cover.jpg',
        images: const ['https://example.org/1.jpg', 'https://example.org/2.jpg'],
        categoryName: 'attraction',
        categoryIcon: 'attractions',
        categoryColor: '#9C27B0',
        destinationId: 'dest-hl-uuid',
        destinationName: 'Hạ Long',
        isVerified: true,
        provenanceCount: 1,
        distanceKm: 1.25,
        openingHours: '24/7',
        website: 'https://example.org',
        phone: '+84 203 123 456',
        source: const PlaceSourceInfo(
          name: 'OpenStreetMap',
          sourceId: 'way/674228542',
          canonicalUrl: 'https://www.openstreetmap.org/way/674228542',
          license: 'ODbL 1.0',
          attribution: '© OpenStreetMap contributors',
        ),
        enrichmentMeta: const PlaceEnrichmentMeta(
          descriptionSourceUrl: 'https://vi.wikipedia.org/wiki/Ha_Long',
          descriptionLicense: 'CC BY-SA 4.0',
          firstImageLicense: 'CC BY 4.0',
          firstImageArtist: 'Nguyen Van A',
        ),
        reviews: [
          PlaceReviewModel(
            id: 'rev-1',
            rating: 5.0,
            content: 'Đẹp vào buổi tối.',
            authorName: 'Minh Anh',
            createdAt: DateTime.utc(2026, 10, 1, 12, 30),
          ),
        ],
      );

      final jsonMap = jsonDecode(jsonEncode(original.toJson())) as Map<String, dynamic>;
      expect(jsonMap['enrichmentMeta']['imageAttributions'], isA<List>());
      expect(
        jsonMap['reviews'][0]['user']['profile']['displayName'],
        'Minh Anh',
      );

      final roundTripped = PlaceModel.fromJson(jsonMap);
      expect(roundTripped.id, original.id);
      expect(roundTripped.name, original.name);
      expect(roundTripped.nameEn, original.nameEn);
      expect(roundTripped.description, original.description);
      expect(roundTripped.address, original.address);
      expect(roundTripped.latitude, original.latitude);
      expect(roundTripped.longitude, original.longitude);
      expect(roundTripped.rating, original.rating);
      expect(roundTripped.reviewCount, original.reviewCount);
      expect(roundTripped.coverImage, original.coverImage);
      expect(roundTripped.images, original.images);
      expect(roundTripped.categoryName, original.categoryName);
      expect(roundTripped.categoryIcon, original.categoryIcon);
      expect(roundTripped.categoryColor, original.categoryColor);
      expect(roundTripped.destinationId, original.destinationId);
      expect(roundTripped.destinationName, original.destinationName);
      expect(roundTripped.isVerified, original.isVerified);
      expect(roundTripped.provenanceCount, original.provenanceCount);
      expect(roundTripped.distanceKm, original.distanceKm);
      expect(roundTripped.openingHours, original.openingHours);
      expect(roundTripped.website, original.website);
      expect(roundTripped.phone, original.phone);
      expect(roundTripped.source?.sourceId, original.source?.sourceId);
      expect(
        roundTripped.enrichmentMeta?.firstImageLicense,
        original.enrichmentMeta?.firstImageLicense,
      );
      expect(
        roundTripped.enrichmentMeta?.firstImageArtist,
        original.enrichmentMeta?.firstImageArtist,
      );
      expect(roundTripped.reviews.single.authorName, 'Minh Anh');
      expect(
        roundTripped.reviews.single.createdAt,
        original.reviews.single.createdAt,
      );
    });
  });

  group('W09-C OfflineTileStore & OfflineTileDownloader', () {
    test('rejects invalid PNG bytes and validates PNG magic header', () async {
      final store = await _createTempStore();
      expect(OfflineTileStore.isValidPng(_valid1x1Png), isTrue);
      expect(
        OfflineTileStore.isValidPng(Uint8List.fromList(utf8.encode('<html>'))),
        isFalse,
      );
      expect(
        () => store.writeTileBytes(
          'ha-long',
          12,
          3266,
          1804,
          Uint8List.fromList(utf8.encode('not-a-png')),
        ),
        throwsFormatException,
      );
    });

    test(
      'downloads 112 tiles with User-Agent, OSM-FR fallback, exact byte count & resume skip',
      () async {
        final store = await _createTempStore();
        final adapter = _MockTileHttpAdapter(
          failPrimaryCondition: (uri) =>
              uri.path.contains('/hot/12/'),
        );
        final dio = Dio()..httpClientAdapter = adapter;
        final downloader = OfflineTileDownloader(
          store: store,
          tileDio: dio,
          placeRepository: _FakeOnlinePlaceRepo(),
          requestDelay: Duration.zero,
          maxConcurrency: 2,
        );

        final progressUpdates = <OfflineDownloadProgress>[];
        final result = await downloader.downloadRegion(
          onProgress: progressUpdates.add,
        );

        expect(result.downloadedTiles, 112);
        expect(result.skippedTiles, 0);
        expect(result.failedTiles, 0);
        expect(result.manifest.tileCount, 112);
        expect(result.manifest.expectedTileCount, 112);
        expect(result.manifest.isComplete, isTrue);
        expect(
          result.manifest.downloadedBytes,
          112 * _valid1x1Png.length,
        );
        expect(result.manifest.places.length, 2);
        expect(
          result.manifest.places.map((p) => p.id),
          containsAll([halongThapDongHoId, halongBaoTangQuangNinhId]),
        );

        // Verify HOT primary and OSM-FR fallback + User-Agent header
        expect(
          adapter.requests.any((r) => r.uri.path.startsWith('/hot/')),
          isTrue,
        );
        expect(
          adapter.requests.any((r) => r.uri.path.startsWith('/osmfr/12/')),
          isTrue,
        );
        for (final req in adapter.requests) {
          expect(
            req.headers['User-Agent'],
            OfflineTileDownloader.defaultUserAgent,
          );
        }

        // Verify manifest persisted on disk and readable after reload
        final loadedManifest = await store.loadManifest('ha-long');
        expect(loadedManifest, isNotNull);
        expect(loadedManifest!.downloadedBytes, 112 * _valid1x1Png.length);
        expect(loadedManifest.tileCount, 112);
        expect(progressUpdates.last.isCompleted, isTrue);

        // Re-running with skipExisting = true issues 0 network requests
        final beforeCount = adapter.requests.length;
        final resumed = await downloader.downloadRegion(skipExisting: true);
        expect(resumed.skippedTiles, 112);
        expect(resumed.downloadedTiles, 0);
        expect(adapter.requests.length, beforeCount);
      },
    );
  });

  group('W09-C CachedOfflineTileProvider', () {
    test('headers map is mutable for TileLayer User-Agent injection', () async {
      final store = await _createTempStore();
      final provider = CachedOfflineTileProvider(store: store);
      expect(
        () => provider.headers.putIfAbsent(
          'User-Agent',
          () => 'flutter_map (com.wanderai.mobile)',
        ),
        returnsNormally,
      );
    });

    testWidgets(
      'serves cached PNG from disk offline and fails uncached tile with OfflineTileUnavailableException',
      (tester) async {
        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await store.writeTileBytes('ha-long', 15, 26131, 14432, _valid1x1Png);
        });

        final offlineDio = Dio()
          ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);
        final provider = CachedOfflineTileProvider(
          store: store,
          dio: offlineDio,
          isOfflineOnly: () => true,
        );
        final layer = TileLayer(
          urlTemplate: OfflineTileDownloader.primaryUrlTemplate,
          fallbackUrl: OfflineTileDownloader.fallbackUrlTemplate,
          subdomains: OfflineTileDownloader.subdomains,
        );

        // Cached tile decodes cleanly offline
        final hitInfo = await tester.runAsync(() async {
          final hitImage = provider.getImage(
            const TileCoordinates(26131, 14432, 15),
            layer,
          );
          final hitCompleter = Completer<ImageInfo>();
          final hitStream = hitImage.resolve(ImageConfiguration.empty);
          late ImageStreamListener hitListener;
          hitListener = ImageStreamListener(
            (info, _) {
              hitCompleter.complete(info);
              hitStream.removeListener(hitListener);
            },
            onError: (err, st) {
              if (!hitCompleter.isCompleted) {
                hitCompleter.completeError(err, st);
              }
            },
          );
          hitStream.addListener(hitListener);
          return hitCompleter.future;
        });
        expect(hitInfo!.image.width, 1);
        expect(hitInfo.image.height, 1);

        // Uncached tile fails cleanly with OfflineTileUnavailableException
        final err = await tester.runAsync(() async {
          final missImage = provider.getImage(
            const TileCoordinates(0, 0, 15),
            layer,
          );
          final missCompleter = Completer<Object>();
          final missStream = missImage.resolve(ImageConfiguration.empty);
          late ImageStreamListener missListener;
          missListener = ImageStreamListener(
            (_, __) {},
            onError: (err, _) {
              if (!missCompleter.isCompleted) missCompleter.complete(err);
              missStream.removeListener(missListener);
            },
          );
          missStream.addListener(missListener);
          return missCompleter.future;
        });
        expect(err, isA<OfflineTileUnavailableException>());
      },
    );

    testWidgets(
      'falls back from HOT to OSM-FR when online and tile is not cached',
      (tester) async {
        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
        });

        final fallbackAdapter = _MockTileHttpAdapter(
          failPrimaryCondition: (uri) => uri.path.startsWith('/hot/'),
        );
        final onlineDio = Dio()..httpClientAdapter = fallbackAdapter;
        final provider = CachedOfflineTileProvider(
          store: store,
          dio: onlineDio,
          isOfflineOnly: () => false,
          cacheEpoch: 1,
        );
        final layer = TileLayer(
          urlTemplate: OfflineTileDownloader.primaryUrlTemplate,
          fallbackUrl: OfflineTileDownloader.fallbackUrlTemplate,
          subdomains: OfflineTileDownloader.subdomains,
        );

        final info = await tester.runAsync(() async {
          final img = provider.getImage(
            const TileCoordinates(26136, 14436, 15),
            layer,
          );
          final completer = Completer<ImageInfo>();
          final stream = img.resolve(ImageConfiguration.empty);
          late ImageStreamListener listener;
          listener = ImageStreamListener(
            (i, _) {
              completer.complete(i);
              stream.removeListener(listener);
            },
            onError: (e, st) {
              if (!completer.isCompleted) completer.completeError(e, st);
            },
          );
          stream.addListener(listener);
          return completer.future;
        });

        expect(info!.image.width, 1);
        expect(
          fallbackAdapter.requests.any((r) => r.uri.path.startsWith('/hot/')),
          isTrue,
        );
        expect(
          fallbackAdapter.requests.any((r) => r.uri.path.startsWith('/osmfr/')),
          isTrue,
        );
      },
    );
  });

  group('W09-C MapNotifier & placeDetailProvider offline cold start', () {
    test(
      'cold-start offline loads cached Halong region + POIs and supports offline search/filter',
      () async {
        final store = await _createTempStore();
        await _seedFullHalongCache(store);

        final container = ProviderContainer(
          overrides: [
            offlineTileStoreProvider.overrideWithValue(store),
            placeRepositoryProvider.overrideWithValue(_OfflineFailingPlaceRepo()),
          ],
        );
        addTearDown(container.dispose);

        final notifier = container.read(mapProvider.notifier);
        await notifier.ensureInitialized();

        final s = container.read(mapProvider);
        expect(s.status, MapLoadingStatus.loaded);
        expect(s.isOfflineMode, isTrue);
        expect(s.activeDestinationSlug, 'ha-long');
        expect(s.places.length, 2);
        expect(
          s.places.map((p) => p.id),
          containsAll([halongThapDongHoId, halongBaoTangQuangNinhId]),
        );
        expect(
          s.cameraRequest!.center.latitude,
          closeTo(20.950, 1e-6),
        );
        expect(
          s.cameraRequest!.center.longitude,
          closeTo(107.0915, 1e-6),
        );
        expect(s.cameraRequest!.zoom, 15.0);

        // Offline text search finds Tháp Đồng Hồ
        await notifier.searchPlaces('Tháp Đồng Hồ');
        final searchState = container.read(mapProvider);
        expect(searchState.status, MapLoadingStatus.loaded);
        expect(searchState.places.single.id, halongThapDongHoId);

        // Clear search returns to cached Hạ Long region
        await notifier.searchPlaces('');
        expect(container.read(mapProvider).places.length, 2);

        // Offline category filter isolates museum (Bảo tàng Quảng Ninh)
        notifier.setCategory('museum');
        final catState = container.read(mapProvider);
        expect(catState.status, MapLoadingStatus.loaded);
        expect(catState.places.single.id, halongBaoTangQuangNinhId);

        // Selecting uncached destination offline shows honest error
        await notifier.selectDestination('ha-noi');
        final hnState = container.read(mapProvider);
        expect(hnState.status, MapLoadingStatus.error);
        expect(hnState.errorMessage, contains('Chưa có dữ liệu ngoại tuyến'));

        // placeDetailProvider falls back to cached POI offline
        final detail = await container.read(
          placeDetailProvider(halongThapDongHoId).future,
        );
        expect(detail.id, halongThapDongHoId);
        expect(detail.name, 'Tháp Đồng Hồ');
      },
    );
  });

  group('W09-C MapScreen offline boundary UI & OfflineMapSheet', () {
    testWidgets(
      'renders PolygonLayer, offline badge, out-of-bbox & out-of-zoom banners, recenter, and OfflineMapSheet',
      (tester) async {
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        final controller = MapController();
        final offlineDio = Dio()
          ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              offlineTileStoreProvider.overrideWithValue(store),
              offlineTileDioProvider.overrideWithValue(offlineDio),
              locationServiceProvider.overrideWithValue(_FakeLocationService()),
              placeRepositoryProvider.overrideWithValue(
                _OfflineFailingPlaceRepo(),
              ),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              home: MapScreen(mapController: controller),
            ),
          ),
        );
        final container = ProviderScope.containerOf(
          tester.element(find.byType(MapScreen)),
        );
        for (var i = 0; i < 20; i++) {
          if (container.read(mapProvider).status == MapLoadingStatus.loaded &&
              container.read(mapProvider).cachedHalongRegion != null) {
            break;
          }
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 20)),
          );
          await tester.pump(const Duration(milliseconds: 50));
        }
        await tester.pump(const Duration(milliseconds: 300));
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 30)),
        );
        await tester.pump(const Duration(milliseconds: 200));

        final debugState = container.read(mapProvider);
        expect(debugState.cachedHalongRegion, isNotNull,
            reason: 'status=${debugState.status}, err=${debugState.errorMessage}, offline=${debugState.isOfflineMode}');
        expect(debugState.status, MapLoadingStatus.loaded);

        // Inside downloaded Hạ Long bbox at z15
        expect(find.byType(PolygonLayer), findsOneWidget);
        expect(find.byKey(const Key('offline_mode_badge')), findsOneWidget);
        expect(find.byKey(const Key('offline_boundary_banner')), findsNothing);
        expect(find.text('2 địa điểm'), findsOneWidget);

        // Pan outside downloaded Hạ Long bbox -> boundary banner + uncached tile placeholder
        controller.move(const LatLng(21.0285, 105.8542), 15.0);
        await tester.pump(const Duration(milliseconds: 200));
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 80)),
        );
        await tester.pump(const Duration(milliseconds: 200));

        expect(find.byKey(const Key('offline_boundary_banner')), findsOneWidget);
        expect(
          find.textContaining('Ngoài vùng bản đồ ngoại tuyến đã tải'),
          findsOneWidget,
        );
        expect(find.byKey(const Key('offline_mode_badge')), findsNothing);
        expect(find.textContaining('Chưa tải'), findsWidgets);

        // Tap recenter CTA -> returns inside Hạ Long bbox
        await tester.tap(find.text('Về Hạ Long'));
        await tester.pump(const Duration(milliseconds: 300));
        expect(
          halongOfflineRegionPreset.bounds.contains(controller.camera.center),
          isTrue,
        );
        expect(find.byKey(const Key('offline_mode_badge')), findsOneWidget);
        expect(find.byKey(const Key('offline_boundary_banner')), findsNothing);

        // Zoom out below z12 -> out-of-zoom boundary banner
        controller.move(halongOfflineRegionPreset.bounds.center, 10.0);
        await tester.pump(const Duration(milliseconds: 200));
        expect(find.byKey(const Key('offline_boundary_banner')), findsOneWidget);
        expect(find.textContaining('Mức zoom hiện tại'), findsOneWidget);

        // Recenter via OfflineMapSheet & verify sheet metadata
        await tester.tap(find.byKey(const Key('offline_map_button')));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));

        expect(find.byType(OfflineMapSheet), findsOneWidget);
        expect(
          find.text(halongOfflineRegionPreset.bounds.formattedLabel),
          findsOneWidget,
        );
        expect(find.text('z12 – z17 (112 mảnh)'), findsOneWidget);
        expect(find.text('112/112 mảnh'), findsOneWidget);
        expect(
          find.textContaining('${112 * _valid1x1Png.length} bytes'),
          findsOneWidget,
        );
        expect(find.byKey(const Key('offline_download_button')), findsOneWidget);
        expect(find.byKey(const Key('offline_recenter_button')), findsOneWidget);
        expect(find.byKey(const Key('offline_delete_button')), findsOneWidget);

        // Delete cache via sheet button -> clears disk manifest & updates sheet UI
        await tester.tap(find.byKey(const Key('offline_delete_button')));
        for (var i = 0; i < 30; i++) {
          if (container.read(mapProvider).cachedHalongRegion == null) break;
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 25)),
          );
          await tester.pump(const Duration(milliseconds: 50));
        }
        await tester.pump(const Duration(milliseconds: 200));

        expect(find.byKey(const Key('offline_cache_summary')), findsNothing);
        expect(find.text('Tải bản đồ ngoại tuyến'), findsOneWidget);
        final remainingManifest = await tester.runAsync(
          () => store.loadManifest(halongOfflineRegionPreset.regionId),
        );
        expect(remainingManifest, isNull);
      },
    );
  });

  group('W09-C Iteration 2 Regression Fixes', () {
    test(
      'rejects truncated PNGs, ignores corrupt files in measureRegionTiles, and repairs on resume',
      () async {
        final store = await _createTempStore();
        // Valid 8-byte PNG header, truncated body (18 bytes, missing IEND).
        final truncatedPng = Uint8List.fromList([
          0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
          0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
          0x00, 0x00,
        ]);
        // Signature + IEND only (20 bytes < 33 minimum PNG length).
        final tooShortPng = Uint8List.fromList([
          0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
          0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
          0xAE, 0x42, 0x60, 0x82,
        ]);
        expect(OfflineTileStore.isValidPng(truncatedPng), isFalse);
        expect(OfflineTileStore.isValidPng(tooShortPng), isFalse);
        expect(OfflineTileStore.isValidPng(_valid1x1Png), isTrue);

        // Write 1 truncated PNG, 1 0-byte PNG, and 1 valid PNG manually.
        final truncatedFile =
            (await store.getTileFile('ha-long', 12, 3266, 1804))!;
        await truncatedFile.parent.create(recursive: true);
        await truncatedFile.writeAsBytes(truncatedPng, flush: true);

        final zeroFile =
            File('${truncatedFile.parent.path}${Platform.pathSeparator}9999.png');
        await zeroFile.writeAsBytes(const <int>[], flush: true);

        await store.writeTileBytes('ha-long', 13, 6532, 3608, _valid1x1Png);

        final measured = await store.measureRegionTiles('ha-long');
        expect(measured.tileCount, 1);
        expect(measured.totalBytes, _valid1x1Png.length);
        expect(await store.hasValidTile('ha-long', 12, 3266, 1804), isFalse);
        expect(
          await store.readTileBytesForRegion('ha-long', 12, 3266, 1804),
          isNull,
        );

        // Downloader(skipExisting: true) repairs the truncated z12 tile.
        final adapter = _MockTileHttpAdapter();
        final dio = Dio()..httpClientAdapter = adapter;
        final downloader = OfflineTileDownloader(
          store: store,
          tileDio: dio,
          placeRepository: _FakeOnlinePlaceRepo(),
          requestDelay: Duration.zero,
          maxConcurrency: 2,
        );
        final result = await downloader.downloadRegion(skipExisting: true);
        expect(result.downloadedTiles, 111);
        expect(result.skippedTiles, 1);
        expect(result.failedTiles, 0);
        expect(await store.hasValidTile('ha-long', 12, 3266, 1804), isTrue);
        final repairedBytes =
            await store.readTileBytesForRegion('ha-long', 12, 3266, 1804);
        expect(repairedBytes, equals(_valid1x1Png));
      },
    );

    testWidgets(
      'online HOT 200 HTML falls back to OSM-FR and corrupt cached PNG fails cleanly offline',
      (tester) async {
        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
        });

        final htmlAdapter = _MockTileHttpAdapter(
          html200Condition: (uri) => uri.path.startsWith('/hot/'),
        );
        final onlineDio = Dio()..httpClientAdapter = htmlAdapter;
        final provider = CachedOfflineTileProvider(
          store: store,
          dio: onlineDio,
          isOfflineOnly: () => false,
          cacheEpoch: 7,
        );
        final layer = TileLayer(
          urlTemplate: OfflineTileDownloader.primaryUrlTemplate,
          fallbackUrl: OfflineTileDownloader.fallbackUrlTemplate,
          subdomains: OfflineTileDownloader.subdomains,
        );

        final info = await tester.runAsync(() async {
          final img = provider.getImage(
            const TileCoordinates(26140, 14440, 15),
            layer,
          );
          final completer = Completer<ImageInfo>();
          final stream = img.resolve(ImageConfiguration.empty);
          late ImageStreamListener listener;
          listener = ImageStreamListener(
            (i, _) {
              completer.complete(i);
              stream.removeListener(listener);
            },
            onError: (e, st) {
              if (!completer.isCompleted) completer.completeError(e, st);
              stream.removeListener(listener);
            },
          );
          stream.addListener(listener);
          return completer.future;
        });
        expect(info!.image.width, 1);
        expect(
          htmlAdapter.requests.any((r) => r.uri.path.startsWith('/hot/')),
          isTrue,
        );
        expect(
          htmlAdapter.requests.any((r) => r.uri.path.startsWith('/osmfr/')),
          isTrue,
        );

        // Corrupt PNG with valid signature + IEND trailer fails decode -> OfflineTileUnavailableException offline.
        await tester.runAsync(() async {
          final fakePng = Uint8List.fromList([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
            0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
            0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44,
            0xAE, 0x42, 0x60, 0x82,
          ]);
          await store.writeTileBytes('ha-long', 15, 100, 200, fakePng);
        });

        final offlineProvider = CachedOfflineTileProvider(
          store: store,
          dio: Dio()..httpClientAdapter = _MockTileHttpAdapter(failAll: true),
          isOfflineOnly: () => true,
        );
        final err = await tester.runAsync(() async {
          final img = offlineProvider.getImage(
            const TileCoordinates(100, 200, 15),
            layer,
          );
          final completer = Completer<Object>();
          final stream = img.resolve(ImageConfiguration.empty);
          late ImageStreamListener listener;
          listener = ImageStreamListener(
            (_, __) {},
            onError: (e, _) {
              if (!completer.isCompleted) completer.complete(e);
              stream.removeListener(listener);
            },
          );
          stream.addListener(listener);
          return completer.future;
        });
        expect(err, isA<OfflineTileUnavailableException>());
      },
    );

    test(
      'offline culture chip includes museum POIs and search supports Vietnamese without diacritics',
      () async {
        final store = await _createTempStore();
        final manifest = await _seedFullHalongCache(store);
        const parkPlace = PlaceModel(
          id: 'park-hl-1',
          name: 'Công viên Sun World Hạ Long',
          latitude: 20.952,
          longitude: 107.089,
          categoryName: 'park',
          destinationId: 'dest-hl-uuid',
          destinationName: 'Hạ Long',
          isVerified: true,
        );
        await store.saveManifest(
          OfflineRegionManifest(
            regionId: manifest.regionId,
            destinationSlug: manifest.destinationSlug,
            name: manifest.name,
            bbox: manifest.bbox,
            minZoom: manifest.minZoom,
            maxZoom: manifest.maxZoom,
            recommendedInitialZoom: manifest.recommendedInitialZoom,
            tileCount: manifest.tileCount,
            expectedTileCount: manifest.expectedTileCount,
            downloadedBytes: manifest.downloadedBytes,
            downloadedAt: manifest.downloadedAt,
            sourceTemplate: manifest.sourceTemplate,
            fallbackTemplate: manifest.fallbackTemplate,
            destination: manifest.destination,
            places: [...manifest.places, parkPlace],
          ),
        );

        final container = ProviderContainer(
          overrides: [
            offlineTileStoreProvider.overrideWithValue(store),
            placeRepositoryProvider.overrideWithValue(_OfflineFailingPlaceRepo()),
          ],
        );
        addTearDown(container.dispose);

        final notifier = container.read(mapProvider.notifier);
        await notifier.ensureInitialized();

        // 'culture' ('Văn hóa') chip returns Bảo tàng Quảng Ninh ('museum').
        notifier.setCategory('culture');
        final cultureState = container.read(mapProvider);
        expect(cultureState.status, MapLoadingStatus.loaded);
        expect(
          cultureState.places.map((p) => p.id),
          equals([halongBaoTangQuangNinhId]),
        );

        // 'nature' ('Thiên nhiên') chip returns 'park' POIs.
        notifier.setCategory('nature');
        expect(
          container.read(mapProvider).places.map((p) => p.id),
          equals(['park-hl-1']),
        );

        // Reset category and search without Vietnamese diacritics.
        notifier.setCategory('all');
        await notifier.searchPlaces('thap dong ho');
        expect(container.read(mapProvider).status, MapLoadingStatus.loaded);
        expect(
          container.read(mapProvider).places.map((p) => p.id),
          equals([halongThapDongHoId]),
        );

        await notifier.searchPlaces('bao tang quang ninh');
        expect(container.read(mapProvider).status, MapLoadingStatus.loaded);
        expect(
          container.read(mapProvider).places.map((p) => p.id),
          equals([halongBaoTangQuangNinhId]),
        );
      },
    );

    test(
      'deleteHalongOfflineRegion cancels active download cleanly and concurrent saveManifest calls never collide',
      () async {
        final store = await _createTempStore();
        final baseManifest = OfflineRegionManifest(
          regionId: halongOfflineRegionPreset.regionId,
          destinationSlug: halongOfflineRegionPreset.destinationSlug,
          name: halongOfflineRegionPreset.name,
          bbox: halongOfflineRegionPreset.bounds,
          minZoom: 12,
          maxZoom: 17,
          recommendedInitialZoom: 15.0,
          tileCount: 1,
          expectedTileCount: 112,
          downloadedBytes: _valid1x1Png.length,
          downloadedAt: DateTime.utc(2026, 11, 25),
          sourceTemplate: OfflineTileDownloader.primaryUrlTemplate,
          fallbackTemplate: OfflineTileDownloader.fallbackUrlTemplate,
          destination: _halongDest(),
          places: [_thapDongHo()],
        );

        // 8 concurrent saveManifest calls must serialize cleanly without PathAccessException.
        await Future.wait(
          List.generate(
            8,
            (i) => store.saveManifest(
              OfflineRegionManifest(
                regionId: baseManifest.regionId,
                destinationSlug: baseManifest.destinationSlug,
                name: baseManifest.name,
                bbox: baseManifest.bbox,
                minZoom: baseManifest.minZoom,
                maxZoom: baseManifest.maxZoom,
                recommendedInitialZoom: baseManifest.recommendedInitialZoom,
                tileCount: i + 1,
                expectedTileCount: 112,
                downloadedBytes: (i + 1) * _valid1x1Png.length,
                downloadedAt: baseManifest.downloadedAt,
                sourceTemplate: baseManifest.sourceTemplate,
                fallbackTemplate: baseManifest.fallbackTemplate,
                destination: baseManifest.destination,
                places: baseManifest.places,
              ),
            ),
          ),
        );
        final loaded = await store.loadManifest('ha-long');
        expect(loaded, isNotNull);
        expect(loaded!.tileCount, 8);

        // Start a slow download and delete mid-flight.
        final slowAdapter = _MockTileHttpAdapter(
          delay: const Duration(milliseconds: 5),
        );
        final downloader = OfflineTileDownloader(
          store: store,
          tileDio: Dio()..httpClientAdapter = slowAdapter,
          placeRepository: _FakeOnlinePlaceRepo(),
          requestDelay: const Duration(milliseconds: 5),
          maxConcurrency: 2,
        );
        final container = ProviderContainer(
          overrides: [
            offlineTileStoreProvider.overrideWithValue(store),
            offlineTileDownloaderProvider.overrideWithValue(downloader),
            placeRepositoryProvider.overrideWithValue(_FakeOnlinePlaceRepo()),
          ],
        );
        addTearDown(container.dispose);

        final notifier = container.read(mapProvider.notifier);
        final downloadFuture = notifier.downloadHalongOfflineRegion();
        await Future<void>.delayed(const Duration(milliseconds: 25));
        await notifier.deleteHalongOfflineRegion();
        await downloadFuture;

        final state = container.read(mapProvider);
        expect(state.isDownloadingOffline, isFalse);
        expect(state.cachedHalongRegion, isNull);
        expect(await store.loadManifest('ha-long'), isNull);
      },
    );

    testWidgets(
      'mid-session online->offline transition renders boundary banner & uncached placeholder and clears back inside',
      (tester) async {
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        final controller = MapController();
        final adapter = _MockTileHttpAdapter(failAll: false);
        final tileDio = Dio()..httpClientAdapter = adapter;
        final downloader = OfflineTileDownloader(
          store: store,
          tileDio: tileDio,
          placeRepository: _FakeOnlinePlaceRepo(),
          requestDelay: Duration.zero,
          maxConcurrency: 2,
        );

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              offlineTileStoreProvider.overrideWithValue(store),
              offlineTileDioProvider.overrideWithValue(tileDio),
              offlineTileDownloaderProvider.overrideWithValue(downloader),
              locationServiceProvider.overrideWithValue(_FakeLocationService()),
              placeRepositoryProvider.overrideWithValue(_FakeOnlinePlaceRepo()),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              home: MapScreen(mapController: controller),
            ),
          ),
        );
        final container = ProviderScope.containerOf(
          tester.element(find.byType(MapScreen)),
        );
        for (var i = 0; i < 20; i++) {
          if (container.read(mapProvider).status != MapLoadingStatus.initial &&
              container.read(mapProvider).status != MapLoadingStatus.loading) {
            break;
          }
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 20)),
          );
          await tester.pump(const Duration(milliseconds: 50));
        }

        // Select Hạ Long online so MapLoadingStatus.loaded + place_count_badge are active.
        await tester.runAsync(
          () => container.read(mapProvider.notifier).selectDestination('ha-long'),
        );
        await tester.pump(const Duration(milliseconds: 100));
        expect(container.read(mapProvider).status, MapLoadingStatus.loaded);
        expect(find.byKey(const Key('place_count_badge')), findsOneWidget);

        // Download Hạ Long while online (isOfflineMode remains false).
        await tester.runAsync(
          () => container.read(mapProvider.notifier).downloadHalongOfflineRegion(),
        );
        await tester.pump(const Duration(milliseconds: 100));
        expect(container.read(mapProvider).isOfflineMode, isFalse);
        expect(container.read(mapProvider).cachedHalongRegion, isNotNull);

        // While still online, panning outside Hạ Long does NOT show offline boundary banner.
        controller.move(const LatLng(16.0544, 108.2022), 15.0);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 60)),
        );
        await tester.pump(const Duration(milliseconds: 100));
        expect(find.byKey(const Key('offline_boundary_banner')), findsNothing);

        // Lose internet mid-session (isOfflineMode still false) and pan slightly to request uncached tiles.
        adapter.failAll = true;
        controller.move(const LatLng(16.1200, 108.2500), 15.0);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 120)),
        );
        await tester.pump(const Duration(milliseconds: 150));

        expect(find.byKey(const Key('offline_boundary_banner')), findsOneWidget);
        expect(find.textContaining('Chưa tải'), findsWidgets);

        // Verify zero overlap between offline_boundary_banner and offline_map_button,
        // my_location_button, PlacePreviewSheet, and place_count_badge when selectedPlace != null at 360x640.
        container.read(mapProvider.notifier).selectPlace(_thapDongHo());
        await tester.pump(const Duration(milliseconds: 100));
        void expectNoBoundaryOverlap() {
          final bannerRect = tester.getRect(
            find.byKey(const Key('offline_boundary_banner')),
          );
          final offlineBtnRect = tester.getRect(
            find.byKey(const Key('offline_map_button')),
          );
          final myLocBtnRect = tester.getRect(
            find.byKey(const Key('my_location_button')),
          );
          final previewRect = tester.getRect(
            find.byType(PlacePreviewSheet),
          );
          expect(
            find.byKey(const Key('place_count_badge')),
            findsNothing,
            reason:
                'place_count_badge hides while boundary banner + preview sheet are both open',
          );
          expect(bannerRect.height, lessThanOrEqualTo(96.0));
          expect(bannerRect.bottom, lessThanOrEqualTo(258.0));
          expect(bannerRect.overlaps(offlineBtnRect), isFalse);
          expect(bannerRect.overlaps(myLocBtnRect), isFalse);
          expect(bannerRect.overlaps(previewRect), isFalse);
          expect(previewRect.overlaps(offlineBtnRect), isFalse);
          expect(previewRect.overlaps(myLocBtnRect), isFalse);
        }

        expectNoBoundaryOverlap();

        // Also check out-of-zoom (z=11.0) at 360x640 with selectedPlace != null.
        controller.move(halongOfflineRegionPreset.bounds.center, 11.0);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 80)),
        );
        await tester.pump(const Duration(milliseconds: 150));

        expect(find.byKey(const Key('offline_boundary_banner')), findsOneWidget);
        expect(find.textContaining('Mức zoom hiện tại'), findsOneWidget);
        expectNoBoundaryOverlap();

        // Recenter back inside Hạ Long -> clears boundary banner cleanly.
        await tester.tap(find.text('Về Hạ Long'));
        await tester.pump(const Duration(milliseconds: 200));
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 60)),
        );
        await tester.pump(const Duration(milliseconds: 150));
        expect(
          halongOfflineRegionPreset.bounds.contains(controller.camera.center),
          isTrue,
        );
        expect(controller.camera.zoom, greaterThanOrEqualTo(12.0));
        expect(find.byKey(const Key('offline_boundary_banner')), findsNothing);
        expect(find.byKey(const Key('place_count_badge')), findsOneWidget);
      },
    );

    testWidgets(
      'cold-start offline 360x640 with selectedPlace != null has zero overlap in out-of-bbox and out-of-zoom states',
      (tester) async {
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        final controller = MapController();
        final offlineDio = Dio()
          ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              offlineTileStoreProvider.overrideWithValue(store),
              offlineTileDioProvider.overrideWithValue(offlineDio),
              locationServiceProvider.overrideWithValue(_FakeLocationService()),
              placeRepositoryProvider.overrideWithValue(
                _OfflineFailingPlaceRepo(),
              ),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              home: MapScreen(mapController: controller),
            ),
          ),
        );
        final container = ProviderScope.containerOf(
          tester.element(find.byType(MapScreen)),
        );
        for (var i = 0; i < 20; i++) {
          if (container.read(mapProvider).status == MapLoadingStatus.loaded &&
              container.read(mapProvider).cachedHalongRegion != null) {
            break;
          }
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 20)),
          );
          await tester.pump(const Duration(milliseconds: 50));
        }
        await tester.pump(const Duration(milliseconds: 200));

        container.read(mapProvider.notifier).selectPlace(_thapDongHo());
        await tester.pump(const Duration(milliseconds: 100));

        void expectNoOverlap() {
          final bannerRect = tester.getRect(
            find.byKey(const Key('offline_boundary_banner')),
          );
          final offlineBtnRect = tester.getRect(
            find.byKey(const Key('offline_map_button')),
          );
          final myLocBtnRect = tester.getRect(
            find.byKey(const Key('my_location_button')),
          );
          final previewRect = tester.getRect(
            find.byType(PlacePreviewSheet),
          );
          expect(
            find.byKey(const Key('place_count_badge')),
            findsNothing,
            reason:
                'place_count_badge hides while boundary banner + preview sheet are both open',
          );
          expect(bannerRect.height, lessThanOrEqualTo(96.0));
          expect(bannerRect.bottom, lessThanOrEqualTo(258.0));
          expect(bannerRect.overlaps(offlineBtnRect), isFalse);
          expect(bannerRect.overlaps(myLocBtnRect), isFalse);
          expect(bannerRect.overlaps(previewRect), isFalse);
          expect(previewRect.overlaps(offlineBtnRect), isFalse);
          expect(previewRect.overlaps(myLocBtnRect), isFalse);
        }

        // Out-of-bbox with selectedPlace != null
        controller.move(const LatLng(16.0544, 108.2022), 15.0);
        await tester.pump(const Duration(milliseconds: 200));
        expect(find.byKey(const Key('offline_boundary_banner')), findsOneWidget);
        expect(
          find.textContaining('Ngoài vùng bản đồ ngoại tuyến đã tải'),
          findsOneWidget,
        );
        expectNoOverlap();

        // Out-of-zoom (z=11.0) with selectedPlace != null
        controller.move(halongOfflineRegionPreset.bounds.center, 11.0);
        await tester.pump(const Duration(milliseconds: 200));
        expect(find.byKey(const Key('offline_boundary_banner')), findsOneWidget);
        expect(find.textContaining('Mức zoom hiện tại'), findsOneWidget);
        expectNoOverlap();

        // Tapping 'Về Hạ Long' recenters cleanly and hides banner
        await tester.tap(find.text('Về Hạ Long'));
        await tester.pump(const Duration(milliseconds: 300));
        expect(
          halongOfflineRegionPreset.bounds.contains(controller.camera.center),
          isTrue,
        );
        expect(controller.camera.zoom, greaterThanOrEqualTo(12.0));
        expect(find.byKey(const Key('offline_boundary_banner')), findsNothing);
        expect(find.byKey(const Key('place_count_badge')), findsOneWidget);
      },
    );
  });

  group('W09-C Iteration 4 Safe-Area Inset & textScaler Regression Fixes', () {
    testWidgets(
      '360x640 with Android safe-area insets (top:24,bottom:24 and top:32,bottom:0) + selectedPlace has zero overlap',
      (tester) async {
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        for (final inset in const [
          EdgeInsets.only(top: 24, bottom: 24),
          EdgeInsets.only(top: 32, bottom: 0),
        ]) {
          final controller = MapController();
          final offlineDio = Dio()
            ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                offlineTileStoreProvider.overrideWithValue(store),
                offlineTileDioProvider.overrideWithValue(offlineDio),
                locationServiceProvider.overrideWithValue(_FakeLocationService()),
                placeRepositoryProvider.overrideWithValue(
                  _OfflineFailingPlaceRepo(),
                ),
              ],
              child: MaterialApp(
                theme: AppTheme.lightTheme,
                builder: (context, child) {
                  final mq = MediaQuery.of(context);
                  return MediaQuery(
                    data: mq.copyWith(padding: inset, viewPadding: inset),
                    child: child!,
                  );
                },
                home: MapScreen(mapController: controller),
              ),
            ),
          );

          final container = ProviderScope.containerOf(
            tester.element(find.byType(MapScreen)),
          );
          for (var i = 0; i < 20; i++) {
            if (container.read(mapProvider).status == MapLoadingStatus.loaded &&
                container.read(mapProvider).cachedHalongRegion != null) {
              break;
            }
            await tester.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 20)),
            );
            await tester.pump(const Duration(milliseconds: 50));
          }
          await tester.pump(const Duration(milliseconds: 200));

          container.read(mapProvider.notifier).selectPlace(_thapDongHo());
          await tester.pump(const Duration(milliseconds: 100));

          // 1. Inside Hạ Long bbox: offline_mode_badge + place_count_badge clear controls & sheet.
          final modeBadgeRect = tester.getRect(
            find.byKey(const Key('offline_mode_badge')),
          );
          final offlineBtnInside = tester.getRect(
            find.byKey(const Key('offline_map_button')),
          );
          final myLocBtnInside = tester.getRect(
            find.byKey(const Key('my_location_button')),
          );
          final countBadgeInside = tester.getRect(
            find.byKey(const Key('place_count_badge')),
          );
          final previewInside = tester.getRect(find.byType(PlacePreviewSheet));

          expect(modeBadgeRect.right, lessThanOrEqualTo(offlineBtnInside.left));
          expect(modeBadgeRect.overlaps(offlineBtnInside), isFalse);
          expect(modeBadgeRect.overlaps(myLocBtnInside), isFalse);
          expect(modeBadgeRect.overlaps(countBadgeInside), isFalse);
          expect(modeBadgeRect.overlaps(previewInside), isFalse);
          expect(countBadgeInside.overlaps(previewInside), isFalse);
          expect(previewInside.overlaps(offlineBtnInside), isFalse);
          expect(previewInside.overlaps(myLocBtnInside), isFalse);

          // 2. Out-of-bbox and out-of-zoom: place_count_badge hidden; banner clears controls & sheet.
          for (final target in const [
            (LatLng(16.0544, 108.2022), 15.0),
            (LatLng(20.950, 107.0915), 11.0),
            (LatLng(20.950, 107.0915), 18.5),
          ]) {
            controller.move(target.$1, target.$2);
            await tester.pump(const Duration(milliseconds: 200));

            expect(
              find.byKey(const Key('offline_boundary_banner')),
              findsOneWidget,
            );
            expect(find.byKey(const Key('place_count_badge')), findsNothing);

            final bannerRect = tester.getRect(
              find.byKey(const Key('offline_boundary_banner')),
            );
            final offlineBtnRect = tester.getRect(
              find.byKey(const Key('offline_map_button')),
            );
            final myLocBtnRect = tester.getRect(
              find.byKey(const Key('my_location_button')),
            );
            final previewRect = tester.getRect(find.byType(PlacePreviewSheet));

            expect(bannerRect.overlaps(offlineBtnRect), isFalse);
            expect(bannerRect.overlaps(myLocBtnRect), isFalse);
            expect(bannerRect.overlaps(previewRect), isFalse);
            expect(previewRect.overlaps(offlineBtnRect), isFalse);
            expect(previewRect.overlaps(myLocBtnRect), isFalse);
          }

          // 3. Recenter CTA restores offline_mode_badge + place_count_badge cleanly.
          await tester.tap(find.text('Về Hạ Long'));
          await tester.pump(const Duration(milliseconds: 250));
          expect(
            find.byKey(const Key('offline_boundary_banner')),
            findsNothing,
          );
          expect(find.byKey(const Key('offline_mode_badge')), findsOneWidget);
          expect(find.byKey(const Key('place_count_badge')), findsOneWidget);

          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pump();
        }
      },
    );

    testWidgets(
      '360x640 with textScaler 1.5 and 2.0 + extreme PlaceModel produces zero RenderFlex overflow and zero overlap',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        const extremePlace = PlaceModel(
          id: 'extreme-place-1',
          name:
              'Bảo tàng Di sản Văn hóa Biển Vịnh Hạ Long Khu vực Trung tâm Hòn Gai Quảng Ninh Mở rộng Đặc biệt Toàn diện',
          address:
              'Đường Trần Quốc Nghiễn kéo dài, Phường Hồng Hải, Thành phố Hạ Long, Tỉnh Quảng Ninh, Việt Nam 200000',
          latitude: 20.9516105,
          longitude: 107.0851999,
          rating: 4.8,
          reviewCount: 256,
          categoryName: 'museum',
          destinationId: 'dest-hl-uuid',
          destinationName: 'Thành phố Du lịch Biển Hạ Long – Quảng Ninh',
          isVerified: true,
          provenanceCount: 2,
        );

        for (final scale in const [1.5, 2.0]) {
          final controller = MapController();
          final offlineDio = Dio()
            ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                offlineTileStoreProvider.overrideWithValue(store),
                offlineTileDioProvider.overrideWithValue(offlineDio),
                locationServiceProvider.overrideWithValue(_FakeLocationService()),
                placeRepositoryProvider.overrideWithValue(
                  _OfflineFailingPlaceRepo(),
                ),
              ],
              child: MaterialApp(
                theme: AppTheme.lightTheme,
                builder: (context, child) {
                  final mq = MediaQuery.of(context);
                  const inset = EdgeInsets.only(top: 24, bottom: 24);
                  return MediaQuery(
                    data: mq.copyWith(
                      padding: inset,
                      viewPadding: inset,
                      textScaler: TextScaler.linear(scale),
                    ),
                    child: child!,
                  );
                },
                home: MapScreen(mapController: controller),
              ),
            ),
          );

          final container = ProviderScope.containerOf(
            tester.element(find.byType(MapScreen)),
          );
          for (var i = 0; i < 20; i++) {
            if (container.read(mapProvider).status == MapLoadingStatus.loaded &&
                container.read(mapProvider).cachedHalongRegion != null) {
              break;
            }
            await tester.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 20)),
            );
            await tester.pump(const Duration(milliseconds: 50));
          }
          await tester.pump(const Duration(milliseconds: 200));

          container.read(mapProvider.notifier).selectPlace(extremePlace);
          await tester.pump(const Duration(milliseconds: 100));

          // Inside bbox: zero overflow & zero overlap.
          final modeBadgeInside = tester.getRect(
            find.byKey(const Key('offline_mode_badge')),
          );
          final offlineBtnInside = tester.getRect(
            find.byKey(const Key('offline_map_button')),
          );
          final myLocBtnInside = tester.getRect(
            find.byKey(const Key('my_location_button')),
          );
          final previewInside = tester.getRect(find.byType(PlacePreviewSheet));
          expect(modeBadgeInside.overlaps(offlineBtnInside), isFalse);
          expect(modeBadgeInside.overlaps(previewInside), isFalse);
          expect(previewInside.overlaps(offlineBtnInside), isFalse);
          expect(previewInside.overlaps(myLocBtnInside), isFalse);

          // Out-of-bbox: zero overflow & zero overlap with boundary banner or controls.
          controller.move(const LatLng(16.0544, 108.2022), 15.0);
          await tester.pump(const Duration(milliseconds: 200));

          final bannerRect = tester.getRect(
            find.byKey(const Key('offline_boundary_banner')),
          );
          final offlineBtnRect = tester.getRect(
            find.byKey(const Key('offline_map_button')),
          );
          final myLocBtnRect = tester.getRect(
            find.byKey(const Key('my_location_button')),
          );
          final previewRect = tester.getRect(find.byType(PlacePreviewSheet));

          expect(bannerRect.overlaps(offlineBtnRect), isFalse);
          expect(bannerRect.overlaps(myLocBtnRect), isFalse);
          expect(bannerRect.overlaps(previewRect), isFalse);
          expect(previewRect.overlaps(offlineBtnRect), isFalse);
          expect(previewRect.overlaps(myLocBtnRect), isFalse);
          expect(find.byKey(const Key('place_count_badge')), findsNothing);

          // Recenter CTA works cleanly even at scale 1.5 / 2.0.
          await tester.tap(find.text('Về Hạ Long'));
          await tester.pump(const Duration(milliseconds: 250));
          expect(
            find.byKey(const Key('offline_boundary_banner')),
            findsNothing,
          );

          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pump();
        }

        expect(
          flutterErrors,
          isEmpty,
          reason:
              'Expected zero Flutter/RenderFlex errors under textScaler 1.5/2.0: $flutterErrors',
        );
      },
    );
  });

  group('W09-C Iteration 5 Layout & Accessibility Regression Fixes', () {
    testWidgets(
      'MapMode.nearby + selectedPlace != null at 360x640 with pad(24,24) and pad(32,24) clears MapCategoryBar and PlacePreviewSheet',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        for (final inset in const [
          EdgeInsets.only(top: 24, bottom: 24),
          EdgeInsets.only(top: 32, bottom: 24),
        ]) {
          for (final scale in const [1.0, 2.0]) {
            final controller = MapController();
            final tileDio = Dio()
              ..httpClientAdapter = _MockTileHttpAdapter(failAll: false);
            final nearbyRepo = _Iter5PlaceRepo([
              _thapDongHo(),
              _baoTangQuangNinh(),
            ]);

            await tester.pumpWidget(
              ProviderScope(
                overrides: [
                  offlineTileStoreProvider.overrideWithValue(store),
                  offlineTileDioProvider.overrideWithValue(tileDio),
                  locationServiceProvider.overrideWithValue(_FakeLocationService()),
                  placeRepositoryProvider.overrideWithValue(nearbyRepo),
                ],
                child: MaterialApp(
                  theme: AppTheme.lightTheme,
                  builder: (context, child) {
                    final mq = MediaQuery.of(context);
                    return MediaQuery(
                      data: mq.copyWith(
                        padding: inset,
                        viewPadding: inset,
                        textScaler: TextScaler.linear(scale),
                      ),
                      child: child!,
                    );
                  },
                  home: MapScreen(mapController: controller),
                ),
              ),
            );

            final container = ProviderScope.containerOf(
              tester.element(find.byType(MapScreen)),
            );
            for (var i = 0; i < 20; i++) {
              if (container.read(mapProvider).status == MapLoadingStatus.loaded &&
                  container.read(mapProvider).cachedHalongRegion != null) {
                break;
              }
              await tester.runAsync(
                () => Future<void>.delayed(const Duration(milliseconds: 20)),
              );
              await tester.pump(const Duration(milliseconds: 50));
            }

            await tester.runAsync(
              () => container.read(mapProvider.notifier).loadNearby(
                    center: const LatLng(20.950, 107.0915),
                  ),
            );
            container.read(mapProvider.notifier).selectPlace(_thapDongHo());
            await tester.pump(const Duration(milliseconds: 150));

            expect(container.read(mapProvider).mode, MapMode.nearby);
            expect(find.byType(MapRadiusSelector), findsOneWidget);

            final catRect = tester.getRect(find.byType(MapCategoryBar));
            final offlineBtnRect = tester.getRect(
              find.byKey(const Key('offline_map_button')),
            );
            final myLocBtnRect = tester.getRect(
              find.byKey(const Key('my_location_button')),
            );
            final radiusRect = tester.getRect(find.byType(MapRadiusSelector));
            final previewRect = tester.getRect(find.byType(PlacePreviewSheet));
            final countBadgeRect = tester.getRect(
              find.byKey(const Key('place_count_badge')),
            );

            expect(
              offlineBtnRect.top,
              greaterThanOrEqualTo(catRect.bottom),
              reason: 'inset=$inset scale=$scale',
            );
            expect(offlineBtnRect.overlaps(catRect), isFalse);
            expect(myLocBtnRect.overlaps(catRect), isFalse);
            expect(radiusRect.overlaps(catRect), isFalse);
            expect(radiusRect.overlaps(offlineBtnRect), isFalse);
            expect(radiusRect.overlaps(myLocBtnRect), isFalse);
            expect(radiusRect.overlaps(previewRect), isFalse);
            expect(radiusRect.overlaps(countBadgeRect), isFalse);
            expect(offlineBtnRect.overlaps(previewRect), isFalse);
            expect(myLocBtnRect.overlaps(previewRect), isFalse);
            expect(countBadgeRect.overlaps(previewRect), isFalse);

            await tester.pumpWidget(const SizedBox.shrink());
            await tester.pump();
          }
        }

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'place_count_badge with 188 POIs at 360x640 textScaler 2.0 never overlaps my_location_button or MapRadiusSelector',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        final places188 = List<PlaceModel>.generate(
          188,
          (i) => i == 0
              ? _thapDongHo()
              : i == 1
                  ? _baoTangQuangNinh()
                  : PlaceModel(
                      id: 'hl-poi-$i',
                      name: 'Địa điểm Hạ Long #$i',
                      latitude: 20.950 + (i % 10) * 0.0005,
                      longitude: 107.085 + (i % 10) * 0.0005,
                      categoryName: 'attraction',
                      destinationId: 'dest-hl-uuid',
                      destinationName: 'Hạ Long',
                      isVerified: true,
                    ),
        );

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          final base = await _seedFullHalongCache(store);
          await store.saveManifest(
            OfflineRegionManifest(
              regionId: base.regionId,
              destinationSlug: base.destinationSlug,
              name: base.name,
              bbox: base.bbox,
              minZoom: base.minZoom,
              maxZoom: base.maxZoom,
              recommendedInitialZoom: base.recommendedInitialZoom,
              tileCount: base.tileCount,
              expectedTileCount: base.expectedTileCount,
              downloadedBytes: base.downloadedBytes,
              downloadedAt: base.downloadedAt,
              sourceTemplate: base.sourceTemplate,
              fallbackTemplate: base.fallbackTemplate,
              destination: base.destination,
              places: places188,
            ),
          );
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        final controller = MapController();
        final offlineDio = Dio()
          ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              offlineTileStoreProvider.overrideWithValue(store),
              offlineTileDioProvider.overrideWithValue(offlineDio),
              locationServiceProvider.overrideWithValue(_FakeLocationService()),
              placeRepositoryProvider.overrideWithValue(
                _OfflineFailingPlaceRepo(),
              ),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              builder: (context, child) {
                final mq = MediaQuery.of(context);
                const inset = EdgeInsets.only(top: 24, bottom: 24);
                return MediaQuery(
                  data: mq.copyWith(
                    padding: inset,
                    viewPadding: inset,
                    textScaler: const TextScaler.linear(2.0),
                  ),
                  child: child!,
                );
              },
              home: MapScreen(mapController: controller),
            ),
          ),
        );

        final container = ProviderScope.containerOf(
          tester.element(find.byType(MapScreen)),
        );
        for (var i = 0; i < 20; i++) {
          if (container.read(mapProvider).status == MapLoadingStatus.loaded &&
              container.read(mapProvider).places.length == 188) {
            break;
          }
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 20)),
          );
          await tester.pump(const Duration(milliseconds: 50));
        }
        await tester.pump(const Duration(milliseconds: 200));

        expect(container.read(mapProvider).places.length, 188);
        expect(find.byKey(const Key('place_count_badge')), findsOneWidget);

        // No selected place
        final countNoSelect = tester.getRect(
          find.byKey(const Key('place_count_badge')),
        );
        final myLocNoSelect = tester.getRect(
          find.byKey(const Key('my_location_button')),
        );
        final offNoSelect = tester.getRect(
          find.byKey(const Key('offline_map_button')),
        );
        expect(countNoSelect.right, lessThanOrEqualTo(myLocNoSelect.left));
        expect(countNoSelect.overlaps(myLocNoSelect), isFalse);
        expect(countNoSelect.overlaps(offNoSelect), isFalse);

        // With selected place
        container.read(mapProvider.notifier).selectPlace(_thapDongHo());
        await tester.pump(const Duration(milliseconds: 100));
        final countSelected = tester.getRect(
          find.byKey(const Key('place_count_badge')),
        );
        final myLocSelected = tester.getRect(
          find.byKey(const Key('my_location_button')),
        );
        final offSelected = tester.getRect(
          find.byKey(const Key('offline_map_button')),
        );
        final previewSelected = tester.getRect(find.byType(PlacePreviewSheet));
        expect(countSelected.right, lessThanOrEqualTo(myLocSelected.left));
        expect(countSelected.overlaps(myLocSelected), isFalse);
        expect(countSelected.overlaps(offSelected), isFalse);
        expect(countSelected.overlaps(previewSelected), isFalse);

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'location_status_pill and denied/deniedForever GPS SnackBar at 360x640 pad(24,24) textScaler 2.0 have zero clipping, overlap, or off-screen error',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        for (final perm in const [
          LocationPermissionState.denied,
          LocationPermissionState.deniedForever,
        ]) {
          final controller = MapController();
          final offlineDio = Dio()
            ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);
          final locSvc = _Iter5LocationService(permission: perm);

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                offlineTileStoreProvider.overrideWithValue(store),
                offlineTileDioProvider.overrideWithValue(offlineDio),
                locationServiceProvider.overrideWithValue(locSvc),
                placeRepositoryProvider.overrideWithValue(
                  _OfflineFailingPlaceRepo(),
                ),
              ],
              child: MaterialApp(
                theme: AppTheme.lightTheme,
                builder: (context, child) {
                  final mq = MediaQuery.of(context);
                  const inset = EdgeInsets.only(top: 24, bottom: 24);
                  return MediaQuery(
                    data: mq.copyWith(
                      padding: inset,
                      viewPadding: inset,
                      textScaler: const TextScaler.linear(2.0),
                    ),
                    child: child!,
                  );
                },
                home: MapScreen(mapController: controller),
              ),
            ),
          );

          final container = ProviderScope.containerOf(
            tester.element(find.byType(MapScreen)),
          );
          for (var i = 0; i < 20; i++) {
            if (container.read(mapProvider).status == MapLoadingStatus.loaded &&
                container.read(mapProvider).cachedHalongRegion != null) {
              break;
            }
            await tester.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 20)),
            );
            await tester.pump(const Duration(milliseconds: 50));
          }
          await tester.pump(const Duration(milliseconds: 200));

          container.read(mapProvider.notifier).selectPlace(_thapDongHo());
          await tester.pump(const Duration(milliseconds: 100));

          await tester.tap(find.byKey(const Key('my_location_button')));
          await tester.pumpAndSettle();

          final pillFinder = find.byKey(const Key('location_status_pill'));
          final countFinder = find.byKey(const Key('place_count_badge'));
          final myLocFinder = find.byKey(const Key('my_location_button'));
          final snackFinder = find.byKey(const Key('map_location_error_snackbar'));
          final sheetFinder = find.byType(PlacePreviewSheet);
          final ctaFinder = find.byKey(const Key('place_preview_view_detail'));

          expect(pillFinder, findsOneWidget);
          expect(countFinder, findsOneWidget);
          expect(snackFinder, findsOneWidget);
          expect(find.text('Mở cài đặt'), findsOneWidget);

          final pillRect = tester.getRect(pillFinder);
          final countRect = tester.getRect(countFinder);
          final myLocRect = tester.getRect(myLocFinder);
          final sheetRect = tester.getRect(sheetFinder);
          final ctaRect = tester.getRect(ctaFinder);
          final snackSurfaceRect = tester.getRect(
            find
                .descendant(of: snackFinder, matching: find.byType(Material))
                .first,
          );

          expect(pillRect.left, greaterThanOrEqualTo(12.0));
          expect(pillRect.right, lessThanOrEqualTo(myLocRect.left));
          expect(pillRect.overlaps(countRect), isFalse);
          expect(pillRect.overlaps(myLocRect), isFalse);
          expect(countRect.overlaps(myLocRect), isFalse);

          expect(snackSurfaceRect.top, greaterThanOrEqualTo(24.0));
          expect(snackSurfaceRect.bottom, lessThanOrEqualTo(sheetRect.top));
          expect(snackSurfaceRect.overlaps(ctaRect), isFalse);

          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pump();
        }

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'OfflineMapSheet at 360x640 pad(24,24) with textScaler 1.3, 1.5, 2.0 produces zero RenderFlex overflow',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        for (final scale in const [1.3, 1.5, 2.0]) {
          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                offlineTileStoreProvider.overrideWithValue(store),
                placeRepositoryProvider.overrideWithValue(
                  _OfflineFailingPlaceRepo(),
                ),
              ],
              child: MaterialApp(
                theme: AppTheme.lightTheme,
                builder: (context, child) {
                  final mq = MediaQuery.of(context);
                  const inset = EdgeInsets.only(top: 24, bottom: 24);
                  return MediaQuery(
                    data: mq.copyWith(
                      padding: inset,
                      viewPadding: inset,
                      textScaler: TextScaler.linear(scale),
                    ),
                    child: child!,
                  );
                },
                home: const Scaffold(body: OfflineMapSheet()),
              ),
            ),
          );

          final container = ProviderScope.containerOf(
            tester.element(find.byType(OfflineMapSheet)),
          );
          await tester.runAsync(
            () => container.read(mapProvider.notifier).refreshOfflineCache(),
          );
          await tester.pump();

          expect(find.byKey(const Key('offline_cache_summary')), findsOneWidget);

          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pump();
        }

        expect(flutterErrors, isEmpty);
      },
    );
  });

  group('W09-C Iteration 6 MapMode.nearby Margin & Banner Regression Fixes', () {
    testWidgets(
      'MapMode.nearby + selectedPlace == null at 360x640 pad(24,24) radiusKm 25.0 with 188 POIs clears MapRadiusSelector with and without location_status_pill at textScaler 1.0 and 2.0',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        final places188 = List<PlaceModel>.generate(
          188,
          (i) => i == 0
              ? _thapDongHo()
              : i == 1
                  ? _baoTangQuangNinh()
                  : PlaceModel(
                      id: 'hl-poi-$i',
                      name: 'Địa điểm Hạ Long #$i',
                      latitude: 20.950 + (i % 10) * 0.0005,
                      longitude: 107.085 + (i % 10) * 0.0005,
                      categoryName: 'attraction',
                      destinationId: 'dest-hl-uuid',
                      destinationName: 'Hạ Long',
                      isVerified: true,
                    ),
        );

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        for (final scale in const [1.0, 2.0]) {
          final controller = MapController();
          final tileDio = Dio()
            ..httpClientAdapter = _MockTileHttpAdapter(failAll: false);
          final nearbyRepo = _Iter5PlaceRepo(places188);

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                offlineTileStoreProvider.overrideWithValue(store),
                offlineTileDioProvider.overrideWithValue(tileDio),
                locationServiceProvider.overrideWithValue(
                  _Iter6GrantedLocationService(),
                ),
                placeRepositoryProvider.overrideWithValue(nearbyRepo),
              ],
              child: MaterialApp(
                theme: AppTheme.lightTheme,
                builder: (context, child) {
                  final mq = MediaQuery.of(context);
                  const inset = EdgeInsets.only(top: 24, bottom: 24);
                  return MediaQuery(
                    data: mq.copyWith(
                      padding: inset,
                      viewPadding: inset,
                      textScaler: TextScaler.linear(scale),
                    ),
                    child: child!,
                  );
                },
                home: MapScreen(mapController: controller),
              ),
            ),
          );

          final container = ProviderScope.containerOf(
            tester.element(find.byType(MapScreen)),
          );
          for (var i = 0; i < 20; i++) {
            if (container.read(mapProvider).status == MapLoadingStatus.loaded &&
                container.read(mapProvider).cachedHalongRegion != null) {
              break;
            }
            await tester.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 20)),
            );
            await tester.pump(const Duration(milliseconds: 50));
          }

          await tester.tap(find.byKey(const Key('my_location_button')));
          await tester.pump(const Duration(milliseconds: 100));
          container.read(mapProvider.notifier).setRadius(25.0);
          await tester.pump(const Duration(milliseconds: 150));

          expect(container.read(mapProvider).mode, MapMode.nearby);
          expect(container.read(mapProvider).selectedPlace, isNull);
          expect(container.read(mapProvider).radiusKm, 25.0);
          expect(container.read(mapProvider).places.length, 188);
          expect(find.byType(MapRadiusSelector), findsOneWidget);
          expect(find.text('25km'), findsOneWidget);
          expect(find.byKey(const Key('place_count_badge')), findsOneWidget);
          expect(find.byKey(const Key('location_status_pill')), findsOneWidget);

          final catRect = tester.getRect(find.byType(MapCategoryBar));
          final offlineBtnRect = tester.getRect(
            find.byKey(const Key('offline_map_button')),
          );
          final myLocBtnRect = tester.getRect(
            find.byKey(const Key('my_location_button')),
          );
          final radiusRect = tester.getRect(find.byType(MapRadiusSelector));
          final countRect = tester.getRect(
            find.byKey(const Key('place_count_badge')),
          );
          final pillRect = tester.getRect(
            find.byKey(const Key('location_status_pill')),
          );

          expect(
            pillRect.overlaps(radiusRect),
            isFalse,
            reason: 'scale=$scale pill=$pillRect radius=$radiusRect',
          );
          expect(
            countRect.overlaps(radiusRect),
            isFalse,
            reason: 'scale=$scale count=$countRect radius=$radiusRect',
          );
          expect(pillRect.overlaps(countRect), isFalse);
          expect(pillRect.right, lessThanOrEqualTo(radiusRect.left));
          expect(countRect.right, lessThanOrEqualTo(radiusRect.left));
          expect(offlineBtnRect.overlaps(catRect), isFalse);
          expect(radiusRect.overlaps(myLocBtnRect), isFalse);

          // Advance past the 5s auto-dismiss timer so location_status_pill hides.
          await tester.pump(const Duration(seconds: 5));
          await tester.pump(const Duration(milliseconds: 100));
          expect(find.byKey(const Key('location_status_pill')), findsNothing);
          expect(find.byKey(const Key('place_count_badge')), findsOneWidget);

          final countRectNoPill = tester.getRect(
            find.byKey(const Key('place_count_badge')),
          );
          final radiusRectNoPill = tester.getRect(
            find.byType(MapRadiusSelector),
          );
          expect(
            countRectNoPill.overlaps(radiusRectNoPill),
            isFalse,
            reason: 'scale=$scale no-pill count=$countRectNoPill radius=$radiusRectNoPill',
          );
          expect(
            countRectNoPill.right,
            lessThanOrEqualTo(radiusRectNoPill.left),
          );

          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pump();
        }

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'MapMode.nearby + selectedPlace != null with offline_mode_badge and offline_boundary_banner (out-of-bbox and z=11.0) at 360x640 pad(24,24) radiusKm 25.0 clears MapRadiusSelector, PlacePreviewSheet, and MapCategoryBar at textScaler 1.0 and 2.0',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        for (final scale in const [1.0, 2.0]) {
          final controller = MapController();
          final offlineDio = Dio()
            ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);
          final repo = _Iter6OfflineNearbyPlaceRepo([
            _thapDongHo(),
            _baoTangQuangNinh(),
          ]);

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                offlineTileStoreProvider.overrideWithValue(store),
                offlineTileDioProvider.overrideWithValue(offlineDio),
                locationServiceProvider.overrideWithValue(_FakeLocationService()),
                placeRepositoryProvider.overrideWithValue(repo),
              ],
              child: MaterialApp(
                theme: AppTheme.lightTheme,
                builder: (context, child) {
                  final mq = MediaQuery.of(context);
                  const inset = EdgeInsets.only(top: 24, bottom: 24);
                  return MediaQuery(
                    data: mq.copyWith(
                      padding: inset,
                      viewPadding: inset,
                      textScaler: TextScaler.linear(scale),
                    ),
                    child: child!,
                  );
                },
                home: MapScreen(mapController: controller),
              ),
            ),
          );

          final container = ProviderScope.containerOf(
            tester.element(find.byType(MapScreen)),
          );
          for (var i = 0; i < 20; i++) {
            final s = container.read(mapProvider);
            if (s.status == MapLoadingStatus.loaded &&
                s.isOfflineMode &&
                s.cachedHalongRegion != null) {
              break;
            }
            await tester.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 20)),
            );
            await tester.pump(const Duration(milliseconds: 50));
          }

          await tester.runAsync(
            () => container.read(mapProvider.notifier).loadNearby(
                  center: const LatLng(20.950, 107.0915),
                  radiusKm: 25.0,
                ),
          );
          container.read(mapProvider.notifier).selectPlace(_thapDongHo());
          await tester.pump(const Duration(milliseconds: 150));

          expect(container.read(mapProvider).isOfflineMode, isTrue);
          expect(container.read(mapProvider).mode, MapMode.nearby);
          expect(container.read(mapProvider).radiusKm, 25.0);
          expect(find.byKey(const Key('offline_mode_badge')), findsOneWidget);
          expect(find.byType(MapRadiusSelector), findsOneWidget);
          expect(find.text('25km'), findsOneWidget);

          final catRectIn = tester.getRect(find.byType(MapCategoryBar));
          final modeBadgeRect = tester.getRect(
            find.byKey(const Key('offline_mode_badge')),
          );
          final radiusRectIn = tester.getRect(find.byType(MapRadiusSelector));
          final previewRectIn = tester.getRect(find.byType(PlacePreviewSheet));
          final offlineBtnRectIn = tester.getRect(
            find.byKey(const Key('offline_map_button')),
          );
          final myLocBtnRectIn = tester.getRect(
            find.byKey(const Key('my_location_button')),
          );

          expect(
            modeBadgeRect.overlaps(radiusRectIn),
            isFalse,
            reason: 'scale=$scale modeBadge=$modeBadgeRect radius=$radiusRectIn',
          );
          expect(
            modeBadgeRect.overlaps(previewRectIn),
            isFalse,
            reason: 'scale=$scale modeBadge=$modeBadgeRect preview=$previewRectIn',
          );
          expect(modeBadgeRect.overlaps(offlineBtnRectIn), isFalse);
          expect(modeBadgeRect.overlaps(myLocBtnRectIn), isFalse);
          expect(offlineBtnRectIn.overlaps(catRectIn), isFalse);
          expect(radiusRectIn.overlaps(previewRectIn), isFalse);

          // Out-of-bbox and out-of-zoom (z=11.0): banner must clear MapRadiusSelector & PlacePreviewSheet.
          for (final target in const [
            (LatLng(16.0544, 108.2022), 15.0),
            (LatLng(20.950, 107.0915), 11.0),
          ]) {
            controller.move(target.$1, target.$2);
            await tester.pump(const Duration(milliseconds: 200));

            expect(
              find.byKey(const Key('offline_boundary_banner')),
              findsOneWidget,
            );
            expect(find.byKey(const Key('place_count_badge')), findsNothing);

            final catRect = tester.getRect(find.byType(MapCategoryBar));
            final bannerRect = tester.getRect(
              find.byKey(const Key('offline_boundary_banner')),
            );
            final radiusRect = tester.getRect(find.byType(MapRadiusSelector));
            final previewRect = tester.getRect(find.byType(PlacePreviewSheet));
            final offlineBtnRect = tester.getRect(
              find.byKey(const Key('offline_map_button')),
            );
            final myLocBtnRect = tester.getRect(
              find.byKey(const Key('my_location_button')),
            );

            expect(
              bannerRect.overlaps(radiusRect),
              isFalse,
              reason: 'target=$target scale=$scale banner=$bannerRect radius=$radiusRect',
            );
            expect(
              bannerRect.overlaps(previewRect),
              isFalse,
              reason: 'target=$target scale=$scale banner=$bannerRect preview=$previewRect',
            );
            expect(bannerRect.overlaps(offlineBtnRect), isFalse);
            expect(bannerRect.overlaps(myLocBtnRect), isFalse);
            expect(offlineBtnRect.overlaps(catRect), isFalse);
            expect(radiusRect.overlaps(previewRect), isFalse);
            expect(previewRect.overlaps(offlineBtnRect), isFalse);
            expect(previewRect.overlaps(myLocBtnRect), isFalse);
          }

          await tester.tap(find.text('Về Hạ Long'));
          await tester.pump(const Duration(milliseconds: 250));
          expect(
            find.byKey(const Key('offline_boundary_banner')),
            findsNothing,
          );
          expect(find.byKey(const Key('offline_mode_badge')), findsOneWidget);

          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pump();
        }

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'location_status_pill is suppressed alongside place_count_badge when showOfflineBoundaryBanner && selectedPlace != null (GPS granted, nearby & destination, pad24 & pad32, textScaler 1.0 & 2.0) and restores on recenter',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        const insets = [
          EdgeInsets.only(top: 24, bottom: 24),
          EdgeInsets.only(top: 32, bottom: 24),
        ];

        for (final mode in const [MapMode.nearby, MapMode.destination]) {
          for (final inset in insets) {
            for (final scale in const [1.0, 2.0]) {
              final controller = MapController();
              final offlineDio = Dio()
                ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);
              final repo = _Iter6OfflineNearbyPlaceRepo([
                _thapDongHo(),
                _baoTangQuangNinh(),
              ]);

              await tester.pumpWidget(
                ProviderScope(
                  overrides: [
                    offlineTileStoreProvider.overrideWithValue(store),
                    offlineTileDioProvider.overrideWithValue(offlineDio),
                    locationServiceProvider.overrideWithValue(
                      _Iter6GrantedLocationService(),
                    ),
                    placeRepositoryProvider.overrideWithValue(repo),
                  ],
                  child: MaterialApp(
                    theme: AppTheme.lightTheme,
                    builder: (context, child) {
                      final mq = MediaQuery.of(context);
                      return MediaQuery(
                        data: mq.copyWith(
                          padding: inset,
                          viewPadding: inset,
                          textScaler: TextScaler.linear(scale),
                        ),
                        child: child!,
                      );
                    },
                    home: MapScreen(mapController: controller),
                  ),
                ),
              );

              final container = ProviderScope.containerOf(
                tester.element(find.byType(MapScreen)),
              );
              for (var i = 0; i < 20; i++) {
                final s = container.read(mapProvider);
                final loc = container.read(userLocationProvider);
                if (s.status == MapLoadingStatus.loaded &&
                    s.isOfflineMode &&
                    s.cachedHalongRegion != null &&
                    loc.label != null) {
                  break;
                }
                await tester.runAsync(
                  () => Future<void>.delayed(const Duration(milliseconds: 20)),
                );
                await tester.pump(const Duration(milliseconds: 50));
              }
              await tester.pump(const Duration(milliseconds: 100));

              expect(
                container.read(userLocationProvider).label,
                isNotNull,
                reason: 'mode=$mode inset=$inset scale=$scale userLoc label',
              );
              expect(
                find.byKey(const Key('location_status_pill')),
                findsOneWidget,
                reason: 'mode=$mode inset=$inset scale=$scale startup pill',
              );

              if (mode == MapMode.nearby) {
                await tester.runAsync(
                  () => container.read(mapProvider.notifier).loadNearby(
                        center: const LatLng(20.950, 107.0915),
                        radiusKm: 25.0,
                      ),
                );
              }
              container.read(mapProvider.notifier).selectPlace(_thapDongHo());
              await tester.pump(const Duration(milliseconds: 150));

              for (final target in const [
                (LatLng(16.0544, 108.2022), 15.0),
                (LatLng(20.950, 107.0915), 11.0),
              ]) {
                controller.move(target.$1, target.$2);
                await tester.pump(const Duration(milliseconds: 200));

                expect(
                  find.byKey(const Key('offline_boundary_banner')),
                  findsOneWidget,
                );
                expect(
                  find.byKey(const Key('location_status_pill')),
                  findsNothing,
                  reason: 'mode=$mode inset=$inset scale=$scale target=$target',
                );
                expect(
                  find.byKey(const Key('place_count_badge')),
                  findsNothing,
                );

                final bannerRect = tester.getRect(
                  find.byKey(const Key('offline_boundary_banner')),
                );
                final previewRect =
                    tester.getRect(find.byType(PlacePreviewSheet));
                final catRect = tester.getRect(find.byType(MapCategoryBar));
                final offlineBtnRect = tester.getRect(
                  find.byKey(const Key('offline_map_button')),
                );
                final myLocBtnRect = tester.getRect(
                  find.byKey(const Key('my_location_button')),
                );

                expect(bannerRect.overlaps(previewRect), isFalse);
                expect(bannerRect.overlaps(catRect), isFalse);
                expect(bannerRect.overlaps(offlineBtnRect), isFalse);
                expect(bannerRect.overlaps(myLocBtnRect), isFalse);
                if (mode == MapMode.nearby) {
                  final radiusRect =
                      tester.getRect(find.byType(MapRadiusSelector));
                  expect(bannerRect.overlaps(radiusRect), isFalse);
                }
              }

              await tester.tap(find.text('Về Hạ Long'));
              await tester.pump(const Duration(milliseconds: 250));
              expect(
                find.byKey(const Key('offline_boundary_banner')),
                findsNothing,
              );
              expect(
                find.byKey(const Key('offline_mode_badge')),
                findsOneWidget,
              );
              expect(
                find.byKey(const Key('location_status_pill')),
                findsOneWidget,
              );
              expect(
                find.byKey(const Key('place_count_badge')),
                findsOneWidget,
              );

              await tester.pumpWidget(const SizedBox.shrink());
              await tester.pump();
            }
          }
        }

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'MapMode.nearby + selectedPlace != null + MapLoadingStatus.empty (in-bounds and with showOfflineBoundaryBanner) at 360x640 pad(32,24) textScaler 2.0 has zero clip past y=640, zero overlap, and zero FlutterError',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        final controller = MapController();
        final offlineDio = Dio()
          ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);
        final repo = _Iter6OfflineNearbyPlaceRepo([
          _thapDongHo(),
          _baoTangQuangNinh(),
        ]);

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              offlineTileStoreProvider.overrideWithValue(store),
              offlineTileDioProvider.overrideWithValue(offlineDio),
              locationServiceProvider.overrideWithValue(_FakeLocationService()),
              placeRepositoryProvider.overrideWithValue(repo),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              builder: (context, child) {
                final mq = MediaQuery.of(context);
                const inset = EdgeInsets.only(top: 32, bottom: 24);
                return MediaQuery(
                  data: mq.copyWith(
                    padding: inset,
                    viewPadding: inset,
                    textScaler: const TextScaler.linear(2.0),
                  ),
                  child: child!,
                );
              },
              home: MapScreen(mapController: controller),
            ),
          ),
        );

        final container = ProviderScope.containerOf(
          tester.element(find.byType(MapScreen)),
        );
        for (var i = 0; i < 20; i++) {
          final s = container.read(mapProvider);
          if (s.status == MapLoadingStatus.loaded &&
              s.isOfflineMode &&
              s.cachedHalongRegion != null) {
            break;
          }
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 20)),
          );
          await tester.pump(const Duration(milliseconds: 50));
        }

        await tester.runAsync(
          () => container.read(mapProvider.notifier).loadNearby(
                center: const LatLng(20.950, 107.0915),
                radiusKm: 25.0,
              ),
        );
        await tester.runAsync(() async {
          container.read(mapProvider.notifier).setCategory('hotel');
          await Future<void>.delayed(const Duration(milliseconds: 20));
        });
        container.read(mapProvider.notifier).selectPlace(_thapDongHo());
        await tester.pump(const Duration(milliseconds: 150));

        expect(container.read(mapProvider).status, MapLoadingStatus.empty);
        expect(container.read(mapProvider).selectedPlace, isNotNull);
        expect(find.byKey(const Key('offline_mode_badge')), findsNothing);
        expect(find.text('Không tìm thấy địa điểm'), findsOneWidget);
        expect(find.byKey(const Key('map_empty_hint')), findsOneWidget);

        // In-bounds empty card is compact, has no SingleChildScrollView occlusion,
        // and fits completely within [194.0 .. previewRect.top] & left of MapRadiusSelector.
        final emptyTitleFinder = find.text('Không tìm thấy địa điểm');
        final emptyHintFinder = find.byKey(const Key('map_empty_hint'));
        expect(
          find.ancestor(
            of: emptyHintFinder,
            matching: find.byType(SingleChildScrollView),
          ),
          findsNothing,
        );
        final emptyTitleRect = tester.getRect(emptyTitleFinder);
        final emptyHintRect = tester.getRect(emptyHintFinder);
        final previewRect = tester.getRect(find.byType(PlacePreviewSheet));
        final radiusRect = tester.getRect(find.byType(MapRadiusSelector));
        expect(emptyTitleRect.top, greaterThanOrEqualTo(194.0));
        expect(emptyHintRect.bottom, lessThanOrEqualTo(previewRect.top));
        expect(emptyHintRect.bottom, lessThanOrEqualTo(640.0));
        expect(emptyTitleRect.right, lessThanOrEqualTo(radiusRect.left));
        expect(emptyHintRect.right, lessThanOrEqualTo(radiusRect.left));

        // Out-of-bounds with showOfflineBoundaryBanner: empty card is suppressed so banner is unobstructed & unclipped.
        controller.move(const LatLng(16.0544, 108.2022), 15.0);
        await tester.pump(const Duration(milliseconds: 200));

        expect(
          find.byKey(const Key('offline_boundary_banner')),
          findsOneWidget,
        );
        expect(find.byKey(const Key('map_empty_hint')), findsNothing);

        final bannerRect = tester.getRect(
          find.byKey(const Key('offline_boundary_banner')),
        );
        final offlineBtnRect = tester.getRect(
          find.byKey(const Key('offline_map_button')),
        );
        final myLocBtnRect = tester.getRect(
          find.byKey(const Key('my_location_button')),
        );
        expect(bannerRect.bottom, lessThanOrEqualTo(640.0));
        expect(bannerRect.overlaps(previewRect), isFalse);
        expect(bannerRect.overlaps(radiusRect), isFalse);
        expect(bannerRect.overlaps(offlineBtnRect), isFalse);
        expect(bannerRect.overlaps(myLocBtnRect), isFalse);

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'Iteration 8 regression: map pan/drag and tap-to-deselect pass through below and beside offline_mode_badge and offline_boundary_banner when selectedPlace != null',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        final controller = MapController();
        final offlineDio = Dio()
          ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              offlineTileStoreProvider.overrideWithValue(store),
              offlineTileDioProvider.overrideWithValue(offlineDio),
              locationServiceProvider.overrideWithValue(_FakeLocationService()),
              placeRepositoryProvider.overrideWithValue(
                _OfflineFailingPlaceRepo(),
              ),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              builder: (context, child) {
                final mq = MediaQuery.of(context);
                const inset = EdgeInsets.only(top: 32, bottom: 24);
                return MediaQuery(
                  data: mq.copyWith(
                    padding: inset,
                    viewPadding: inset,
                  ),
                  child: child!,
                );
              },
              home: MapScreen(mapController: controller),
            ),
          ),
        );

        final container = ProviderScope.containerOf(
          tester.element(find.byType(MapScreen)),
        );
        for (var i = 0; i < 20; i++) {
          final s = container.read(mapProvider);
          if (s.status == MapLoadingStatus.loaded &&
              s.isOfflineMode &&
              s.cachedHalongRegion != null) {
            break;
          }
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 20)),
          );
          await tester.pump(const Duration(milliseconds: 50));
        }

        container.read(mapProvider.notifier).selectPlace(_thapDongHo());
        await tester.pump(const Duration(milliseconds: 150));

        expect(find.byKey(const Key('offline_mode_badge')), findsOneWidget);
        expect(find.byType(PlacePreviewSheet), findsOneWidget);

        // 1. Tap beside offline_mode_badge passes through and dismisses PlacePreviewSheet.
        final badgeRect =
            tester.getRect(find.byKey(const Key('offline_mode_badge')));
        await tester.tapAt(Offset(badgeRect.right + 20, badgeRect.center.dy));
        await tester.pump(const Duration(milliseconds: 400));
        expect(container.read(mapProvider).selectedPlace, isNull);
        expect(find.byType(PlacePreviewSheet), findsNothing);

        // 2. Re-select, drag in empty map band below offline_mode_badge moves map camera,
        //    then tap at (250, 350) dismisses PlacePreviewSheet.
        container.read(mapProvider.notifier).selectPlace(_thapDongHo());
        await tester.pump(const Duration(milliseconds: 150));
        final centerBefore = controller.camera.center;
        await tester.dragFrom(const Offset(250, 350), const Offset(0, -80));
        await tester.pump(const Duration(seconds: 1));
        final centerAfter = controller.camera.center;
        expect(
          (centerAfter.latitude - centerBefore.latitude).abs() +
              (centerAfter.longitude - centerBefore.longitude).abs(),
          greaterThan(1e-5),
        );

        await tester.tapAt(const Offset(250, 350));
        await tester.pump(const Duration(milliseconds: 400));
        expect(container.read(mapProvider).selectedPlace, isNull);
        expect(find.byType(PlacePreviewSheet), findsNothing);

        // 3. Out-of-bounds with showOfflineBoundaryBanner && selectedPlace != null:
        //    drag & tap below banner pass straight through to FlutterMap.
        container.read(mapProvider.notifier).selectPlace(_thapDongHo());
        controller.move(const LatLng(16.0544, 108.2022), 15.0);
        await tester.pump(const Duration(milliseconds: 200));

        expect(
          find.byKey(const Key('offline_boundary_banner')),
          findsOneWidget,
        );
        final oobBefore = controller.camera.center;
        await tester.dragFrom(const Offset(200, 400), const Offset(0, -80));
        await tester.pump(const Duration(seconds: 1));
        final oobAfter = controller.camera.center;
        expect(
          (oobAfter.latitude - oobBefore.latitude).abs() +
              (oobAfter.longitude - oobBefore.longitude).abs(),
          greaterThan(1e-5),
        );

        await tester.tapAt(const Offset(200, 400));
        await tester.pump(const Duration(milliseconds: 400));
        expect(container.read(mapProvider).selectedPlace, isNull);
        expect(find.byType(PlacePreviewSheet), findsNothing);

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'Iteration 8 regression: MapLoadingStatus.error with selectedPlace != null at 360x640 pad(32,24) textScaler 2.0 (GPS denied & granted) has 0 overflow, hides location_status_pill, and Thử lại is visible and tappable',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        for (final gpsGranted in const [false, true]) {
          final controller = MapController();
          final offlineDio = Dio()
            ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);
          final repo = _Iter8FlakyNearbyPlaceRepo(
            nearbyPlaces: [_thapDongHo(), _baoTangQuangNinh()],
          );

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                offlineTileStoreProvider.overrideWithValue(store),
                offlineTileDioProvider.overrideWithValue(offlineDio),
                locationServiceProvider.overrideWithValue(
                  gpsGranted
                      ? _Iter6GrantedLocationService()
                      : _FakeLocationService(),
                ),
                placeRepositoryProvider.overrideWithValue(repo),
              ],
              child: MaterialApp(
                theme: AppTheme.lightTheme,
                builder: (context, child) {
                  final mq = MediaQuery.of(context);
                  const inset = EdgeInsets.only(top: 32, bottom: 24);
                  return MediaQuery(
                    data: mq.copyWith(
                      padding: inset,
                      viewPadding: inset,
                      textScaler: const TextScaler.linear(2.0),
                    ),
                    child: child!,
                  );
                },
                home: MapScreen(mapController: controller),
              ),
            ),
          );

          final container = ProviderScope.containerOf(
            tester.element(find.byType(MapScreen)),
          );
          for (var i = 0; i < 20; i++) {
            final s = container.read(mapProvider);
            final loc = container.read(userLocationProvider);
            if (s.status == MapLoadingStatus.loaded &&
                s.isOfflineMode &&
                s.cachedHalongRegion != null &&
                (!gpsGranted || loc.label != null)) {
              break;
            }
            await tester.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 20)),
            );
            await tester.pump(const Duration(milliseconds: 50));
          }

          await tester.runAsync(
            () => container.read(mapProvider.notifier).loadNearby(
                  center: const LatLng(20.950, 107.0915),
                  radiusKm: 25.0,
                ),
          );
          container.read(mapProvider.notifier).selectPlace(_thapDongHo());
          await tester.pump(const Duration(milliseconds: 150));

          expect(container.read(mapProvider).mode, MapMode.nearby);
          expect(container.read(mapProvider).status, MapLoadingStatus.error);
          expect(container.read(mapProvider).selectedPlace, isNotNull);
          expect(find.byKey(const Key('location_status_pill')), findsNothing);
          expect(find.byKey(const Key('offline_mode_badge')), findsNothing);
          expect(find.byType(AppStateBanner), findsOneWidget);
          expect(find.text('Thử lại'), findsOneWidget);

          final bannerRect = tester.getRect(find.byType(AppStateBanner));
          final retryRect = tester.getRect(find.text('Thử lại'));
          final previewRect = tester.getRect(find.byType(PlacePreviewSheet));
          final radiusRect = tester.getRect(find.byType(MapRadiusSelector));

          expect(bannerRect.top, greaterThanOrEqualTo(194.0));
          expect(bannerRect.bottom, lessThanOrEqualTo(previewRect.top));
          expect(bannerRect.bottom, lessThanOrEqualTo(640.0));
          expect(bannerRect.right, lessThanOrEqualTo(radiusRect.left));
          expect(retryRect.top, greaterThanOrEqualTo(194.0));
          expect(retryRect.bottom, lessThanOrEqualTo(previewRect.top));
          expect(retryRect.right, lessThanOrEqualTo(radiusRect.left));

          // Tap 'Thử lại' (with default warnIfMissed: true) -> triggers retry and recovers.
          await tester.runAsync(() async {
            await tester.tap(find.text('Thử lại'));
            await Future<void>.delayed(const Duration(milliseconds: 50));
          });
          await tester.pump(const Duration(milliseconds: 150));

          expect(repo.nearbyCalls, 2);
          expect(container.read(mapProvider).status, MapLoadingStatus.loaded);
          if (gpsGranted) {
            expect(
              find.byKey(const Key('location_status_pill')),
              findsOneWidget,
            );
          }

          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pump();
        }

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'Iteration 8 regression: in-bounds MapLoadingStatus.empty & loading with selectedPlace != null and GPS granted at 360x640 pad(32,24) textScaler 2.0 suppress location_status_pill and stay unclipped',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        final controller = MapController();
        final offlineDio = Dio()
          ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);
        final loadingGate = Completer<void>();
        final repo = _Iter8GatedNearbyPlaceRepo(
          nearbyPlaces: [_thapDongHo(), _baoTangQuangNinh()],
          gate: loadingGate,
        );

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              offlineTileStoreProvider.overrideWithValue(store),
              offlineTileDioProvider.overrideWithValue(offlineDio),
              locationServiceProvider.overrideWithValue(
                _Iter6GrantedLocationService(),
              ),
              placeRepositoryProvider.overrideWithValue(repo),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              builder: (context, child) {
                final mq = MediaQuery.of(context);
                const inset = EdgeInsets.only(top: 32, bottom: 24);
                return MediaQuery(
                  data: mq.copyWith(
                    padding: inset,
                    viewPadding: inset,
                    textScaler: const TextScaler.linear(2.0),
                  ),
                  child: child!,
                );
              },
              home: MapScreen(mapController: controller),
            ),
          ),
        );

        final container = ProviderScope.containerOf(
          tester.element(find.byType(MapScreen)),
        );
        for (var i = 0; i < 20; i++) {
          final s = container.read(mapProvider);
          final loc = container.read(userLocationProvider);
          if (s.status == MapLoadingStatus.loaded &&
              s.isOfflineMode &&
              s.cachedHalongRegion != null &&
              loc.label != null) {
            break;
          }
          await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 20)),
          );
          await tester.pump(const Duration(milliseconds: 50));
        }

        // 1. Trigger MapLoadingStatus.loading while selectedPlace != null + GPS granted.
        //    (Call selectPlace after loadNearby starts, because loadNearby resets selectedPlace.)
        final nearbyFuture = container.read(mapProvider.notifier).loadNearby(
              center: const LatLng(20.950, 107.0915),
              radiusKm: 25.0,
            );
        container.read(mapProvider.notifier).selectPlace(_thapDongHo());
        await tester.pump(const Duration(milliseconds: 50));

        expect(container.read(mapProvider).status, MapLoadingStatus.loading);
        expect(find.byKey(const Key('location_status_pill')), findsNothing);
        expect(find.byKey(const Key('offline_mode_badge')), findsNothing);
        expect(find.text('Đang tải địa điểm...'), findsOneWidget);

        final loadingRect = tester.getRect(find.text('Đang tải địa điểm...'));
        final previewRect = tester.getRect(find.byType(PlacePreviewSheet));
        final radiusRect = tester.getRect(find.byType(MapRadiusSelector));
        expect(loadingRect.top, greaterThanOrEqualTo(194.0));
        expect(loadingRect.bottom, lessThanOrEqualTo(previewRect.top));
        expect(loadingRect.right, lessThanOrEqualTo(radiusRect.left));

        // Out-of-bounds while loading + selectedPlace != null suppresses loading chip.
        controller.move(const LatLng(16.0544, 108.2022), 15.0);
        await tester.pump(const Duration(milliseconds: 100));
        expect(find.text('Đang tải địa điểm...'), findsNothing);
        expect(
          find.byKey(const Key('offline_boundary_banner')),
          findsOneWidget,
        );

        // Recenter & complete loading.
        await tester.tap(find.text('Về Hạ Long'));
        await tester.pump(const Duration(milliseconds: 100));
        loadingGate.complete();
        await tester.runAsync(() => nearbyFuture);
        await tester.pump(const Duration(milliseconds: 150));

        // 2. Re-enter MapMode.nearby and trigger MapLoadingStatus.empty with selectedPlace != null + GPS granted.
        //    (recenterToOfflineRegion switches back to destination mode when activeDestinationSlug differs.)
        final secondNearby = container.read(mapProvider.notifier).loadNearby(
              center: const LatLng(20.950, 107.0915),
              radiusKm: 25.0,
            );
        await tester.runAsync(() => secondNearby);
        await tester.pump(const Duration(milliseconds: 100));
        await tester.runAsync(() async {
          container.read(mapProvider.notifier).setCategory('hotel');
          await Future<void>.delayed(const Duration(milliseconds: 20));
        });
        container.read(mapProvider.notifier).selectPlace(_thapDongHo());
        await tester.pump(const Duration(milliseconds: 150));

        expect(container.read(mapProvider).mode, MapMode.nearby);
        expect(container.read(mapProvider).status, MapLoadingStatus.empty);
        expect(container.read(mapProvider).selectedPlace, isNotNull);
        expect(find.byKey(const Key('location_status_pill')), findsNothing);
        expect(find.byKey(const Key('offline_mode_badge')), findsNothing);
        expect(find.text('Không tìm thấy địa điểm'), findsOneWidget);
        expect(find.byKey(const Key('map_empty_hint')), findsOneWidget);

        final emptyTitleRect =
            tester.getRect(find.text('Không tìm thấy địa điểm'));
        final emptyHintRect =
            tester.getRect(find.byKey(const Key('map_empty_hint')));
        final nearbyRadiusRect = tester.getRect(find.byType(MapRadiusSelector));
        expect(emptyTitleRect.top, greaterThanOrEqualTo(194.0));
        expect(emptyHintRect.bottom, lessThanOrEqualTo(previewRect.top));
        expect(emptyHintRect.bottom, lessThanOrEqualTo(640.0));
        expect(emptyTitleRect.right, lessThanOrEqualTo(nearbyRadiusRect.left));
        expect(emptyHintRect.right, lessThanOrEqualTo(nearbyRadiusRect.left));

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'Iteration 9 regression: selectedPlace == null + MapLoadingStatus.error (MapMode.nearby 102-char DioException & MapMode.destination offline da-nang 77-char) at 360x640 pad(32,24) textScaler 2.0 with GPS granted + offline_mode_badge has 0 overflow, 0 overlap, and Thử lại is visible and tappable',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        for (final mode in const [MapMode.nearby, MapMode.destination]) {
          final controller = MapController();
          final offlineDio = Dio()
            ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);
          final repo = _Iter9FlakyPlaceRepo(
            places: [_thapDongHo(), _baoTangQuangNinh()],
          );

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                offlineTileStoreProvider.overrideWithValue(store),
                offlineTileDioProvider.overrideWithValue(offlineDio),
                locationServiceProvider.overrideWithValue(
                  _Iter6GrantedLocationService(),
                ),
                placeRepositoryProvider.overrideWithValue(repo),
              ],
              child: MaterialApp(
                theme: AppTheme.lightTheme,
                builder: (context, child) {
                  final mq = MediaQuery.of(context);
                  const inset = EdgeInsets.only(top: 32, bottom: 24);
                  return MediaQuery(
                    data: mq.copyWith(
                      padding: inset,
                      viewPadding: inset,
                      textScaler: const TextScaler.linear(2.0),
                    ),
                    child: child!,
                  );
                },
                home: MapScreen(mapController: controller),
              ),
            ),
          );

          final container = ProviderScope.containerOf(
            tester.element(find.byType(MapScreen)),
          );
          for (var i = 0; i < 20; i++) {
            final s = container.read(mapProvider);
            final loc = container.read(userLocationProvider);
            if (s.status == MapLoadingStatus.loaded &&
                s.isOfflineMode &&
                s.cachedHalongRegion != null &&
                loc.label != null) {
              break;
            }
            await tester.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 20)),
            );
            await tester.pump(const Duration(milliseconds: 50));
          }
          await tester.pump(const Duration(milliseconds: 100));

          if (mode == MapMode.nearby) {
            await tester.runAsync(
              () => container.read(mapProvider.notifier).loadNearby(
                    center: const LatLng(20.950, 107.0915),
                    radiusKm: 25.0,
                  ),
            );
            await tester.pump(const Duration(milliseconds: 150));
            expect(
              container.read(mapProvider).errorMessage?.length,
              104,
              reason: 'Expected full 104-char capped DioException message',
            );
          } else {
            await tester.runAsync(
              () => container
                  .read(mapProvider.notifier)
                  .selectDestination('da-nang'),
            );
            await tester.pump(const Duration(milliseconds: 150));
            expect(
              container.read(mapProvider).errorMessage,
              'Chưa có dữ liệu ngoại tuyến cho khu vực này. Hãy mở vùng Hạ Long đã tải.',
            );
          }

          final state = container.read(mapProvider);
          expect(state.mode, mode);
          expect(state.status, MapLoadingStatus.error);
          expect(state.selectedPlace, isNull);
          expect(find.byKey(const Key('offline_mode_badge')), findsOneWidget);
          expect(find.byKey(const Key('location_status_pill')), findsOneWidget);
          expect(find.byType(AppStateBanner), findsOneWidget);
          expect(find.text('Thử lại'), findsOneWidget);

          final badgeRect =
              tester.getRect(find.byKey(const Key('offline_mode_badge')));
          final bannerRect = tester.getRect(find.byType(AppStateBanner));
          final retryRect = tester.getRect(find.text('Thử lại'));
          final offBtnRect =
              tester.getRect(find.byKey(const Key('offline_map_button')));
          final locBtnRect =
              tester.getRect(find.byKey(const Key('my_location_button')));
          final pillRect =
              tester.getRect(find.byKey(const Key('location_status_pill')));

          expect(bannerRect.top, greaterThanOrEqualTo(badgeRect.bottom));
          expect(bannerRect.top, greaterThanOrEqualTo(194.0));
          expect(bannerRect.bottom, lessThanOrEqualTo(530.0));
          expect(bannerRect.bottom, lessThanOrEqualTo(616.0));
          expect(bannerRect.overlaps(offBtnRect), isFalse);
          expect(bannerRect.overlaps(locBtnRect), isFalse);
          expect(bannerRect.overlaps(pillRect), isFalse);

          expect(retryRect.top, greaterThanOrEqualTo(194.0));
          expect(retryRect.bottom, lessThanOrEqualTo(530.0));
          expect(retryRect.bottom, lessThanOrEqualTo(616.0));
          expect(retryRect.overlaps(offBtnRect), isFalse);
          expect(retryRect.overlaps(locBtnRect), isFalse);
          expect(retryRect.overlaps(pillRect), isFalse);

          if (mode == MapMode.nearby) {
            final radRect = tester.getRect(find.byType(MapRadiusSelector));
            expect(bannerRect.right, lessThanOrEqualTo(radRect.left));
            expect(bannerRect.overlaps(radRect), isFalse);
            expect(retryRect.right, lessThanOrEqualTo(radRect.left));
            expect(retryRect.overlaps(radRect), isFalse);
          } else {
            expect(bannerRect.right, lessThanOrEqualTo(offBtnRect.left));
            expect(retryRect.right, lessThanOrEqualTo(offBtnRect.left));
          }

          // Allow destination retry to succeed on second attempt as well.
          repo.failDestinations = false;
          await tester.runAsync(() async {
            await tester.tap(find.text('Thử lại'));
            await Future<void>.delayed(const Duration(milliseconds: 50));
          });
          await tester.pump(const Duration(milliseconds: 150));

          if (mode == MapMode.nearby) {
            expect(repo.nearbyCalls, 2);
          } else {
            expect(repo.destinationPlaceCalls, greaterThanOrEqualTo(1));
          }
          expect(container.read(mapProvider).status, MapLoadingStatus.loaded);
          expect(find.byKey(const Key('location_status_pill')), findsOneWidget);

          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pump();
        }

        expect(flutterErrors, isEmpty);
      },
    );

    testWidgets(
      'Iteration 9 regression: selectedPlace == null + MapLoadingStatus.empty & loading (MapMode.nearby & MapMode.destination) at 360x640 pad(32,24) textScaler 2.0 with GPS granted + offline_mode_badge stay unclipped inside [194..530] with 0 overlap and 0 FlutterError',
      (tester) async {
        final flutterErrors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          if (details.library == 'image resource service' &&
              details.exception is OfflineTileUnavailableException) {
            return;
          }
          flutterErrors.add(details);
          prevOnError?.call(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        late OfflineTileStore store;
        await tester.runAsync(() async {
          store = await _createTempStore();
          await _seedFullHalongCache(store);
        });

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(tester.view.reset);

        for (final mode in const [MapMode.nearby, MapMode.destination]) {
          final controller = MapController();
          final offlineDio = Dio()
            ..httpClientAdapter = _MockTileHttpAdapter(failAll: true);
          final loadingGate = Completer<void>();
          final repo = _Iter8GatedNearbyPlaceRepo(
            nearbyPlaces: [_thapDongHo(), _baoTangQuangNinh()],
            gate: loadingGate,
          );

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                offlineTileStoreProvider.overrideWithValue(store),
                offlineTileDioProvider.overrideWithValue(offlineDio),
                locationServiceProvider.overrideWithValue(
                  _Iter6GrantedLocationService(),
                ),
                placeRepositoryProvider.overrideWithValue(repo),
              ],
              child: MaterialApp(
                theme: AppTheme.lightTheme,
                builder: (context, child) {
                  final mq = MediaQuery.of(context);
                  const inset = EdgeInsets.only(top: 32, bottom: 24);
                  return MediaQuery(
                    data: mq.copyWith(
                      padding: inset,
                      viewPadding: inset,
                      textScaler: const TextScaler.linear(2.0),
                    ),
                    child: child!,
                  );
                },
                home: MapScreen(mapController: controller),
              ),
            ),
          );

          final container = ProviderScope.containerOf(
            tester.element(find.byType(MapScreen)),
          );
          for (var i = 0; i < 20; i++) {
            final s = container.read(mapProvider);
            final loc = container.read(userLocationProvider);
            if (s.status == MapLoadingStatus.loaded &&
                s.isOfflineMode &&
                s.cachedHalongRegion != null &&
                loc.label != null) {
              break;
            }
            await tester.runAsync(
              () => Future<void>.delayed(const Duration(milliseconds: 20)),
            );
            await tester.pump(const Duration(milliseconds: 50));
          }
          await tester.pump(const Duration(milliseconds: 100));

          // 1. Check MapLoadingStatus.loading with selectedPlace == null in MapMode.nearby.
          if (mode == MapMode.nearby) {
            final nearbyFuture = container.read(mapProvider.notifier).loadNearby(
                  center: const LatLng(20.950, 107.0915),
                  radiusKm: 25.0,
                );
            await tester.pump(const Duration(milliseconds: 50));

            expect(container.read(mapProvider).status, MapLoadingStatus.loading);
            expect(container.read(mapProvider).selectedPlace, isNull);
            expect(find.byKey(const Key('offline_mode_badge')), findsOneWidget);
            expect(find.byKey(const Key('location_status_pill')), findsOneWidget);
            expect(find.text('Đang tải địa điểm...'), findsOneWidget);

            final badgeRect =
                tester.getRect(find.byKey(const Key('offline_mode_badge')));
            final loadingRect =
                tester.getRect(find.text('Đang tải địa điểm...'));
            final offBtnRect =
                tester.getRect(find.byKey(const Key('offline_map_button')));
            final locBtnRect =
                tester.getRect(find.byKey(const Key('my_location_button')));
            final radRect = tester.getRect(find.byType(MapRadiusSelector));
            final pillRect =
                tester.getRect(find.byKey(const Key('location_status_pill')));

            expect(loadingRect.top, greaterThanOrEqualTo(badgeRect.bottom));
            expect(loadingRect.bottom, lessThanOrEqualTo(530.0));
            expect(loadingRect.right, lessThanOrEqualTo(radRect.left));
            expect(loadingRect.overlaps(offBtnRect), isFalse);
            expect(loadingRect.overlaps(locBtnRect), isFalse);
            expect(loadingRect.overlaps(radRect), isFalse);
            expect(loadingRect.overlaps(pillRect), isFalse);

            loadingGate.complete();
            await tester.runAsync(() => nearbyFuture);
            await tester.pump(const Duration(milliseconds: 100));
          }

          // 2. Check MapLoadingStatus.empty with selectedPlace == null.
          await tester.runAsync(() async {
            container.read(mapProvider.notifier).setCategory('hotel');
            await Future<void>.delayed(const Duration(milliseconds: 20));
          });
          await tester.pump(const Duration(milliseconds: 150));

          final state = container.read(mapProvider);
          expect(state.mode, mode);
          expect(state.status, MapLoadingStatus.empty);
          expect(state.selectedPlace, isNull);
          expect(find.byKey(const Key('offline_mode_badge')), findsOneWidget);
          expect(find.byKey(const Key('location_status_pill')), findsOneWidget);
          expect(find.text('Không tìm thấy địa điểm'), findsOneWidget);
          expect(find.byKey(const Key('map_empty_hint')), findsOneWidget);

          final badgeRect =
              tester.getRect(find.byKey(const Key('offline_mode_badge')));
          final emptyTitleRect =
              tester.getRect(find.text('Không tìm thấy địa điểm'));
          final emptyHintRect =
              tester.getRect(find.byKey(const Key('map_empty_hint')));
          final emptyCardFinder = find
              .ancestor(
                of: find.byKey(const Key('map_empty_hint')),
                matching: find.byType(Container),
              )
              .first;
          final emptyCardRect = tester.getRect(emptyCardFinder);
          final offBtnRect =
              tester.getRect(find.byKey(const Key('offline_map_button')));
          final locBtnRect =
              tester.getRect(find.byKey(const Key('my_location_button')));
          final pillRect =
              tester.getRect(find.byKey(const Key('location_status_pill')));

          expect(emptyCardRect.top, greaterThanOrEqualTo(badgeRect.bottom));
          expect(emptyCardRect.top, greaterThanOrEqualTo(194.0));
          expect(emptyCardRect.bottom, lessThanOrEqualTo(530.0));
          expect(emptyCardRect.bottom, lessThanOrEqualTo(616.0));
          expect(emptyTitleRect.top, greaterThanOrEqualTo(194.0));
          expect(emptyHintRect.bottom, lessThanOrEqualTo(530.0));
          expect(emptyCardRect.overlaps(offBtnRect), isFalse);
          expect(emptyCardRect.overlaps(locBtnRect), isFalse);
          expect(emptyCardRect.overlaps(pillRect), isFalse);

          if (mode == MapMode.nearby) {
            final radRect = tester.getRect(find.byType(MapRadiusSelector));
            expect(emptyCardRect.right, lessThanOrEqualTo(radRect.left));
            expect(emptyCardRect.overlaps(radRect), isFalse);
          } else {
            expect(emptyCardRect.right, lessThanOrEqualTo(offBtnRect.left));
          }

          await tester.pumpWidget(const SizedBox.shrink());
          await tester.pump();
        }

        expect(flutterErrors, isEmpty);
      },
    );
  });
}

class _Iter9FlakyPlaceRepo extends _OfflineFailingPlaceRepo {
  final List<PlaceModel> places;
  int nearbyCalls = 0;
  int destinationPlaceCalls = 0;
  bool failDestinations = true;

  _Iter9FlakyPlaceRepo({required this.places});

  @override
  Future<List<DestinationModel>> getDestinations({int limit = 50}) async {
    if (failDestinations) {
      return super.getDestinations(limit: limit);
    }
    return const [
      DestinationModel(
        id: 'dest-hn',
        slug: 'ha-noi',
        name: 'Hà Nội',
        latitude: 21.0285,
        longitude: 105.8542,
      ),
      DestinationModel(
        id: 'dest-dn',
        slug: 'da-nang',
        name: 'Đà Nẵng',
        latitude: 16.0544,
        longitude: 108.2022,
      ),
      DestinationModel(
        id: 'dest-hl-uuid',
        slug: 'ha-long',
        name: 'Hạ Long',
        latitude: 20.9101,
        longitude: 107.1839,
      ),
    ];
  }

  @override
  Future<List<PlaceModel>> getPlaces({
    int page = 1,
    int limit = 50,
    String? search,
    String? category,
    String? destinationId,
    bool verifiedOnly = true,
  }) async {
    if (failDestinations) {
      return super.getPlaces(
        page: page,
        limit: limit,
        search: search,
        category: category,
        destinationId: destinationId,
        verifiedOnly: verifiedOnly,
      );
    }
    destinationPlaceCalls++;
    return places;
  }

  @override
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10,
    int limit = 50,
    bool verifiedOnly = true,
  }) async {
    nearbyCalls++;
    if (nearbyCalls == 1) {
      throw DioException(
        requestOptions: RequestOptions(path: '/places/nearby'),
        type: DioExceptionType.connectionError,
        message: 'Simulated nearby connection failure exceeding 80 chars cap',
      );
    }
    return places;
  }
}

class _Iter8FlakyNearbyPlaceRepo extends _OfflineFailingPlaceRepo {
  final List<PlaceModel> nearbyPlaces;
  int nearbyCalls = 0;
  _Iter8FlakyNearbyPlaceRepo({required this.nearbyPlaces});

  @override
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10,
    int limit = 50,
    bool verifiedOnly = true,
  }) async {
    nearbyCalls++;
    if (nearbyCalls == 1) {
      throw Exception('Simulated nearby network error');
    }
    return nearbyPlaces;
  }
}

class _Iter8GatedNearbyPlaceRepo extends _OfflineFailingPlaceRepo {
  final List<PlaceModel> nearbyPlaces;
  final Completer<void> gate;
  _Iter8GatedNearbyPlaceRepo({
    required this.nearbyPlaces,
    required this.gate,
  });

  @override
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10,
    int limit = 50,
    bool verifiedOnly = true,
  }) async {
    await gate.future;
    return nearbyPlaces;
  }
}

class _Iter6GrantedLocationService extends _FakeLocationService {
  @override
  Future<LocationPermissionState> checkPermission() async =>
      LocationPermissionState.granted;

  @override
  Future<LocationPermissionState> requestPermission() async =>
      LocationPermissionState.granted;

  @override
  Future<bool> isServiceEnabled() async => true;
}

class _Iter6OfflineNearbyPlaceRepo extends _OfflineFailingPlaceRepo {
  final List<PlaceModel> nearbyPlaces;
  _Iter6OfflineNearbyPlaceRepo(this.nearbyPlaces);

  @override
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10,
    int limit = 50,
    bool verifiedOnly = true,
  }) async =>
      nearbyPlaces;
}

class _Iter5PlaceRepo extends _FakeOnlinePlaceRepo {
  final List<PlaceModel> nearbyPlaces;
  _Iter5PlaceRepo(this.nearbyPlaces);

  @override
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10,
    int limit = 50,
    bool verifiedOnly = true,
  }) async =>
      nearbyPlaces;
}

class _Iter5LocationService extends _FakeLocationService {
  final LocationPermissionState permission;
  _Iter5LocationService({required this.permission});

  @override
  Future<LocationPermissionState> checkPermission() async => permission;

  @override
  Future<LocationPermissionState> requestPermission() async => permission;

  @override
  Future<bool> isServiceEnabled() async => false;

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;
}
