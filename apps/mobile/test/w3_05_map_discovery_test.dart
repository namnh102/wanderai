import 'dart:async';
import 'dart:math' as math;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/features/home/presentation/home_screen.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/map/data/destination_model.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/map/data/place_repository.dart';
import 'package:wanderai_mobile/features/map/presentation/map_screen.dart';
import 'package:wanderai_mobile/features/map/providers/map_provider.dart';

import 'location_navigation_test.dart' show FakeLocationService;

// ── Fixtures ──

const hnId = 'id-hn';
const dnId = 'id-dn';
const hlId = 'id-hl';

// Deliberately NOT the app default centre: proves coordinates come from the API.
List<DestinationModel> backendDestinations() => const [
      DestinationModel(
          id: hnId, slug: 'ha-noi', name: 'Hà Nội', latitude: 21.0, longitude: 105.8),
      DestinationModel(
          id: dnId, slug: 'da-nang', name: 'Đà Nẵng', latitude: 16.05, longitude: 108.2),
      DestinationModel(
          id: hlId, slug: 'ha-long', name: 'Hạ Long', latitude: 20.95, longitude: 107.08),
    ];

PlaceModel place(String id, double lat, double lng,
        {String category = 'attraction'}) =>
    PlaceModel(
      id: id,
      name: 'Place $id',
      categoryName: category,
      latitude: lat,
      longitude: lng,
      isVerified: true,
    );

List<PlaceModel> many(String prefix, int n, double lat, double lng,
        {String category = 'attraction'}) =>
    List.generate(
        n, (i) => place('$prefix$i', lat + i * 1e-4, lng + i * 1e-4, category: category));

/// Fake repository with per-request gates so tests can reorder responses.
class ControlledRepo implements PlaceRepository {
  List<DestinationModel> destinations = backendDestinations();
  final Map<String, List<PlaceModel>> byDestination = {};
  final Map<String, List<PlaceModel>> bySearch = {};
  final Map<String, Completer<void>> gates = {};
  final Set<String> failOnce = {};
  final List<Map<String, Object?>> placeCalls = [];
  int nearbyCalls = 0;
  int destinationCalls = 0;

  Completer<void> gate(String key) => gates[key] = Completer<void>();

  @override
  Future<List<DestinationModel>> getDestinations({int limit = 50}) async {
    destinationCalls++;
    return destinations;
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
    placeCalls.add({
      'page': page,
      'limit': limit,
      'search': search,
      'category': category,
      'destinationId': destinationId,
      'verifiedOnly': verifiedOnly,
    });
    final key = search != null ? 'search:$search' : 'dest:$destinationId';
    final g = gates[key];
    if (g != null) await g.future;
    if (failOnce.remove(key)) throw Exception('boom');
    var all = search != null
        ? (bySearch[search] ?? [])
        : (byDestination[destinationId] ?? []);
    if (category != null) {
      all = all.where((p) => p.categoryName == category).toList();
    }
    final start = (page - 1) * limit;
    if (start >= all.length) return [];
    return all.sublist(start, math.min(start + limit, all.length));
  }

  @override
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10,
    int limit = 100,
    bool verifiedOnly = true,
    String? category,
  }) async {
    nearbyCalls++;
    return [place('near1', lat, lng)];
  }

  @override
  Future<PlaceModel> getPlaceById(String id) async => throw UnimplementedError();

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

ControlledRepo seededRepo() {
  final r = ControlledRepo();
  r.byDestination[hnId] = many('hn', 145, 21.0, 105.8);
  r.byDestination[dnId] = many('dn', 293, 16.05, 108.2);
  r.byDestination[hlId] = many('hl', 188, 20.95, 107.08);
  return r;
}

ProviderContainer containerFor(ControlledRepo repo) {
  final c = ProviderContainer(
      overrides: [placeRepositoryProvider.overrideWithValue(repo)]);
  addTearDown(c.dispose);
  return c;
}

Future<void> flush() => Future<void>.delayed(Duration.zero);

/// Widget test whose network tile failures (flutter_test blocks real HTTP and
/// answers 400) are ignored. Every other framework error still fails the test.
void testMap(String name, Future<void> Function(WidgetTester) body) {
  testWidgets(name, (tester) async {
    final old = FlutterError.onError;
    FlutterError.onError = (details) {
      if (details.library == 'image resource service') return;
      old?.call(details);
    };
    try {
      await body(tester);
    } finally {
      FlutterError.onError = old;
    }
  });
}

void main() {
  group('W3-05 destination source of truth', () {
    test('A. DestinationModel parses id/slug/name/lat/lon (num or string)', () {
      final d = DestinationModel.fromJson({
        'id': 'x',
        'slug': 'ha-noi',
        'name': 'Hà Nội',
        'latitude': '21.0285',
        'longitude': 105.8542,
      });
      expect(d.id, 'x');
      expect(d.slug, 'ha-noi');
      expect(d.latitude, 21.0285);
      expect(d.longitude, 105.8542);
      expect(d.hasValidCoordinates, isTrue);
    });

    test('B. exactly the three supported slugs, no ids/coords hardcoded', () {
      expect(supportedDestinations.map((e) => e.slug).toList(),
          ['ha-noi', 'da-nang', 'ha-long']);
      expect(supportedDestinations.map((e) => e.label).toList(),
          ['Hà Nội', 'Đà Nẵng', 'Hạ Long']);
    });

    test('C. missing / duplicate / invalid-coordinate destinations are explicit errors', () {
      final ok = backendDestinations();
      expect(resolveSupportedDestinations(ok).keys,
          containsAll(['ha-noi', 'da-nang', 'ha-long']));
      expect(() => resolveSupportedDestinations(ok.sublist(0, 2)),
          throwsA(isA<DestinationResolutionException>()));
      expect(() => resolveSupportedDestinations([...ok, ok.first]),
          throwsA(isA<DestinationResolutionException>()));
      expect(
          () => resolveSupportedDestinations([
                ok[0],
                ok[1],
                const DestinationModel(id: 'z', slug: 'ha-long', name: 'x'),
              ]),
          throwsA(isA<DestinationResolutionException>()));
    });

    test('C2. notifier surfaces a readable error and does not fall back', () async {
      final repo = seededRepo()..destinations = backendDestinations().sublist(0, 2);
      final c = containerFor(repo);
      await c.read(mapProvider.notifier).selectDestination('ha-noi');
      final s = c.read(mapProvider);
      expect(s.status, MapLoadingStatus.error);
      expect(s.errorMessage, contains('Hạ Long'));
      expect(s.places, isEmpty);
      expect(repo.placeCalls, isEmpty);
    });
  });

  group('W3-05 destination browse', () {
    test('D. pagination walks limit=100 pages until exhausted, unique', () async {
      final repo = seededRepo();
      final all = await repo.getAllPlacesForDestination(destinationId: dnId);
      expect(all.length, 293);
      expect(all.map((p) => p.id).toSet().length, 293);
      expect(repo.placeCalls.map((c) => c['page']).toList(), [1, 2, 3]);
    });

    test('D2. duplicates across pages are removed', () async {
      final repo = seededRepo();
      repo.byDestination[hnId] = [
        ...many('a', 100, 21.0, 105.8),
        ...many('a', 10, 21.0, 105.8), // same ids again
      ];
      final all = await repo.getAllPlacesForDestination(destinationId: hnId);
      expect(all.length, 100);
    });

    test('E/F. destinationId + verifiedOnly are sent; camera goes to backend coords', () async {
      final repo = seededRepo();
      final c = containerFor(repo);
      await c.read(mapProvider.notifier).ensureInitialized();
      final s = c.read(mapProvider);
      expect(s.mode, MapMode.destination);
      expect(s.activeDestinationSlug, 'ha-noi');
      expect(s.places.length, 145);
      expect(s.status, MapLoadingStatus.loaded);
      expect(repo.placeCalls.every((c) => c['destinationId'] == hnId), isTrue);
      expect(repo.placeCalls.every((c) => c['verifiedOnly'] == true), isTrue);
      expect(repo.placeCalls.every((c) => c['search'] == null), isTrue);
      expect(s.cameraRequest!.center, const LatLng(21.0, 105.8));
    });

    test('G. HN / DN / HL each load their own unique set (145/293/188)', () async {
      final repo = seededRepo();
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      for (final e in {'ha-noi': 145, 'da-nang': 293, 'ha-long': 188}.entries) {
        await n.selectDestination(e.key);
        final s = c.read(mapProvider);
        expect(s.places.length, e.value, reason: e.key);
        expect(s.places.map((p) => p.id).toSet().length, e.value);
        expect(s.places.every((p) => p.id.startsWith(e.key == 'ha-noi' ? 'hn' : e.key == 'da-nang' ? 'dn' : 'hl')), isTrue);
      }
      expect(c.read(mapProvider).cameraRequest!.center, const LatLng(20.95, 107.08));
    });

    test('H. mode transitions: destination → search → clear → last destination', () async {
      final repo = seededRepo();
      repo.bySearch['Pizza Halong'] = [place('pz', 20.96, 107.09)];
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      await n.selectDestination('da-nang');
      await n.searchPlaces('Pizza Halong');
      var s = c.read(mapProvider);
      expect(s.mode, MapMode.search);
      expect(s.activeDestinationSlug, isNull); // neutral
      expect(s.lastBrowseSlug, 'da-nang');
      await n.searchPlaces('');
      s = c.read(mapProvider);
      expect(s.mode, MapMode.destination);
      expect(s.activeDestinationSlug, 'da-nang');
      expect(s.searchQuery, isNull);
      expect(s.places.length, 293);
      expect(s.cameraRequest!.center, const LatLng(16.05, 108.2));
    });

    test('H2. selecting a destination during search leaves search mode', () async {
      final repo = seededRepo();
      repo.bySearch['q'] = [place('a', 1, 1), place('b', 2, 2)];
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      await n.searchPlaces('q');
      await n.selectDestination('ha-long');
      final s = c.read(mapProvider);
      expect(s.mode, MapMode.destination);
      expect(s.searchQuery, isNull);
      expect(s.activeDestinationSlug, 'ha-long');
      expect(s.places.length, 188);
    });
  });

  group('W3-05 search camera', () {
    test('I. search is global (no destinationId), verified only', () async {
      final repo = seededRepo();
      repo.bySearch['Pizza'] = [place('a', 1, 1), place('b', 2, 2)];
      final c = containerFor(repo);
      await c.read(mapProvider.notifier).searchPlaces('Pizza');
      final call = repo.placeCalls.single;
      expect(call['destinationId'], isNull);
      expect(call['search'], 'Pizza');
      expect(call['verifiedOnly'], true);
    });

    test('J. zero results: empty state, no camera request, no selection', () async {
      final repo = seededRepo();
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      await n.selectDestination('ha-noi');
      final before = c.read(mapProvider).cameraRequest!.seq;
      await n.searchPlaces('zzqxwv');
      final s = c.read(mapProvider);
      expect(s.status, MapLoadingStatus.empty);
      expect(s.places, isEmpty);
      expect(s.selectedPlace, isNull);
      expect(s.cameraRequest!.seq, before);
    });

    test('K. exactly one result: camera request to its coordinates + auto-select', () async {
      final repo = seededRepo();
      repo.bySearch['Pizza Halong'] = [place('pz', 20.9511, 107.0733)];
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      await n.selectDestination('ha-noi');
      final before = c.read(mapProvider).cameraRequest!.seq;
      await n.searchPlaces('Pizza Halong');
      final s = c.read(mapProvider);
      expect(s.selectedPlace?.id, 'pz');
      expect(s.cameraRequest!.seq, greaterThan(before));
      expect(s.cameraRequest!.center, const LatLng(20.9511, 107.0733));
      expect(s.cameraRequest!.zoom, singleResultZoom);
      expect(s.cameraRequest!.fitPoints, isEmpty);
    });

    test('L. 2+ results: fit request over all points, nothing auto-selected', () async {
      final repo = seededRepo();
      repo.bySearch['Cafe'] = [place('a', 21, 105.8), place('b', 16, 108.2), place('c', 20.9, 107)];
      final c = containerFor(repo);
      await c.read(mapProvider.notifier).searchPlaces('Cafe');
      final s = c.read(mapProvider);
      expect(s.selectedPlace, isNull);
      expect(s.places.length, 3);
      expect(s.cameraRequest!.fitPoints.length, 3);
    });
  });

  group('W3-05 stale response protection', () {
    test('M. HN slow, DN fast → final state is DN', () async {
      final repo = seededRepo();
      final hnGate = repo.gate('dest:$hnId');
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      final f1 = n.selectDestination('ha-noi');
      await flush();
      final f2 = n.selectDestination('da-nang');
      await f2;
      hnGate.complete();
      await f1;
      final s = c.read(mapProvider);
      expect(s.activeDestinationSlug, 'da-nang');
      expect(s.places.length, 293);
      expect(s.places.first.id.startsWith('dn'), isTrue);
    });

    test('M2. rapid HN → DN → HL ends with only HL (188)', () async {
      final repo = seededRepo();
      repo.gate('dest:$hnId');
      repo.gate('dest:$dnId');
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      final f1 = n.selectDestination('ha-noi');
      await flush();
      final f2 = n.selectDestination('da-nang');
      await flush();
      final f3 = n.selectDestination('ha-long');
      await f3;
      repo.gates['dest:$hnId']!.complete();
      repo.gates['dest:$dnId']!.complete();
      await Future.wait([f1, f2]);
      final s = c.read(mapProvider);
      expect(s.places.length, 188);
      expect(s.places.every((p) => p.id.startsWith('hl')), isTrue);
      expect(s.cameraRequest!.center, const LatLng(20.95, 107.08));
    });

    test('N. late "Pizza" is ignored after "Pizza Halong"', () async {
      final repo = seededRepo();
      repo.bySearch['Pizza'] = [place('x', 1, 1), place('y', 2, 2)];
      repo.bySearch['Pizza Halong'] = [place('pz', 20.95, 107.07)];
      final slow = repo.gate('search:Pizza');
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      final f1 = n.searchPlaces('Pizza');
      await flush();
      await n.searchPlaces('Pizza Halong');
      slow.complete();
      await f1;
      final s = c.read(mapProvider);
      expect(s.searchQuery, 'Pizza Halong');
      expect(s.places.map((p) => p.id), ['pz']);
      expect(s.selectedPlace?.id, 'pz');
    });

    test('O. search in flight then select Hạ Long → late search ignored', () async {
      final repo = seededRepo();
      repo.bySearch['Pizza'] = [place('x', 1, 1), place('y', 2, 2)];
      final slow = repo.gate('search:Pizza');
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      final f1 = n.searchPlaces('Pizza');
      await flush();
      await n.selectDestination('ha-long');
      final camSeq = c.read(mapProvider).cameraRequest!.seq;
      slow.complete();
      await f1;
      final s = c.read(mapProvider);
      expect(s.mode, MapMode.destination);
      expect(s.places.length, 188);
      expect(s.searchQuery, isNull);
      expect(s.cameraRequest!.seq, camSeq); // no late camera jump
    });
  });

  group('W3-05 category and retry', () {
    test('P. category is applied per mode and never revives stale rows', () async {
      final repo = seededRepo();
      repo.byDestination[hnId] = [
        ...many('r', 5, 21, 105.8, category: 'restaurant'),
        ...many('h', 7, 21, 105.8, category: 'hotel'),
      ];
      repo.bySearch['q'] = [
        place('s1', 1, 1, category: 'restaurant'),
        place('s2', 2, 2, category: 'restaurant'),
        place('s3', 3, 3, category: 'hotel'),
      ];
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);

      // browse: server-side category + destinationId
      await n.selectDestination('ha-noi');
      repo.placeCalls.clear();
      n.setCategory('restaurant');
      await flush();
      await flush();
      expect(repo.placeCalls.last['category'], 'restaurant');
      expect(repo.placeCalls.last['destinationId'], hnId);
      expect(c.read(mapProvider).places.length, 5);
      n.setCategory('all');
      await flush();
      await flush();
      expect(c.read(mapProvider).places.length, 12);

      // search: global + category
      await n.searchPlaces('q');
      repo.placeCalls.clear();
      n.setCategory('restaurant');
      await flush();
      await flush();
      expect(repo.placeCalls.last['search'], 'q');
      expect(repo.placeCalls.last['destinationId'], isNull);
      expect(repo.placeCalls.last['category'], 'restaurant');
      expect(c.read(mapProvider).places.length, 2);
    });

    test('P2. rapid category change: late old category response is ignored', () async {
      final repo = seededRepo();
      repo.byDestination[hnId] = [
        ...many('r', 5, 21, 105.8, category: 'restaurant'),
        ...many('h', 7, 21, 105.8, category: 'hotel'),
      ];
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      await n.selectDestination('ha-noi');
      final g = repo.gate('dest:$hnId');
      n.setCategory('restaurant');
      await flush();
      repo.gates.remove('dest:$hnId');
      n.setCategory('hotel');
      await flush();
      await flush();
      g.complete();
      await flush();
      await flush();
      final s = c.read(mapProvider);
      expect(s.selectedCategory, 'hotel');
      expect(s.places.length, 7);
      expect(s.places.every((p) => p.categoryName == 'hotel'), isTrue);
    });

    test('Q. retry repeats the failed operation without changing mode', () async {
      final repo = seededRepo();
      repo.bySearch['Pizza'] = [place('x', 1, 1), place('y', 2, 2)];
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);

      await n.selectDestination('da-nang');
      repo.failOnce.add('dest:$dnId');
      await n.selectDestination('da-nang');
      expect(c.read(mapProvider).status, MapLoadingStatus.error);
      await n.retry();
      expect(c.read(mapProvider).status, MapLoadingStatus.loaded);
      expect(c.read(mapProvider).activeDestinationSlug, 'da-nang');
      expect(c.read(mapProvider).places.length, 293);

      repo.failOnce.add('search:Pizza');
      await n.searchPlaces('Pizza');
      expect(c.read(mapProvider).status, MapLoadingStatus.error);
      expect(c.read(mapProvider).mode, MapMode.search);
      await n.retry();
      expect(c.read(mapProvider).mode, MapMode.search);
      expect(c.read(mapProvider).places.length, 2);
    });

    test('R. user location enters NEARBY mode and clears search/highlight', () async {
      final repo = seededRepo();
      repo.bySearch['q'] = [place('a', 1, 1), place('b', 2, 2)];
      final c = containerFor(repo);
      final n = c.read(mapProvider.notifier);
      await n.selectDestination('ha-noi');
      await n.searchPlaces('q');
      n.setUserLocation(const LatLng(10, 106));
      await flush();
      final s = c.read(mapProvider);
      expect(s.mode, MapMode.nearby);
      expect(s.searchQuery, isNull);
      expect(s.activeDestinationSlug, isNull);
      expect(s.lastBrowseSlug, 'ha-noi');
      expect(repo.nearbyCalls, 1);
    });
  });

  group('W3-05 MapScreen widget behaviour', () {
    Future<(MapController, ControlledRepo, ProviderContainer)> pumpScreen(
        WidgetTester tester) async {
      tester.view.physicalSize = const Size(1200, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      final repo = seededRepo();
      final controller = MapController();
      await tester.pumpWidget(ProviderScope(
        overrides: [
          locationServiceProvider.overrideWithValue(FakeLocationService()),
          placeRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: MapScreen(mapController: controller)),
      ));
      await tester.pump(const Duration(milliseconds: 300));
      await tester.pump(const Duration(milliseconds: 300));
      final c = ProviderScope.containerOf(tester.element(find.byType(MapScreen)));
      return (controller, repo, c);
    }

    bool chipSelected(WidgetTester tester, String slug) => tester
        .widget<ChoiceChip>(find.byKey(Key('map_destination_chip_$slug')))
        .selected;

    testMap('S1. first load: Hà Nội selected, camera at backend coords', (tester) async {
      final (controller, _, c) = await pumpScreen(tester);
      expect(c.read(mapProvider).places.length, 145);
      expect(chipSelected(tester, 'ha-noi'), isTrue);
      expect(controller.camera.center.latitude, closeTo(21.0, 1e-6));
      expect(controller.camera.center.longitude, closeTo(105.8, 1e-6));
      expect(find.text('145 địa điểm'), findsOneWidget);
    });

    testMap('S2. chip tap switches destination, camera and count; search text cleared', (tester) async {
      final (controller, repo, c) = await pumpScreen(tester);
      repo.bySearch['abc'] = [place('a', 1, 1), place('b', 2, 2)];
      await tester.enterText(find.byType(TextField), 'abc');
      await tester.pump(const Duration(milliseconds: 600));
      await tester.pump();
      expect(c.read(mapProvider).mode, MapMode.search);
      expect(chipSelected(tester, 'ha-noi'), isFalse); // neutral in SEARCH
      expect(chipSelected(tester, 'da-nang'), isFalse);

      await tester.tap(find.byKey(const Key('map_destination_chip_da-nang')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));
      expect(c.read(mapProvider).mode, MapMode.destination);
      expect(c.read(mapProvider).places.length, 293);
      expect(chipSelected(tester, 'da-nang'), isTrue);
      expect(tester.widget<TextField>(find.byType(TextField)).controller!.text, '');
      expect(controller.camera.center.latitude, closeTo(16.05, 1e-6));
      expect(controller.camera.center.longitude, closeTo(108.2, 1e-6));
    });

    testMap('S3. single search result moves the camera, selects, shows preview', (tester) async {
      final (controller, repo, c) = await pumpScreen(tester);
      repo.bySearch['Pizza Halong'] = [place('pz', 20.9511, 107.0733)];
      final before = controller.camera.center;
      c.read(mapProvider.notifier).searchPlaces('Pizza Halong');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(before.longitude, isNot(closeTo(107.0733, 1e-3)));
      expect(controller.camera.center.latitude, closeTo(20.9511, 1e-6));
      expect(controller.camera.center.longitude, closeTo(107.0733, 1e-6));
      expect(controller.camera.zoom, singleResultZoom);
      expect(c.read(mapProvider).selectedPlace?.id, 'pz');
      expect(find.text('Place pz'), findsWidgets); // preview sheet
    });

    testMap('S4. multiple results fit the camera; none auto-selected', (tester) async {
      final (controller, repo, c) = await pumpScreen(tester);
      repo.bySearch['Cafe'] = [place('a', 21.03, 105.85), place('b', 21.10, 105.95)];
      c.read(mapProvider.notifier).searchPlaces('Cafe');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      final cam = controller.camera;
      expect(c.read(mapProvider).selectedPlace, isNull);
      expect(cam.visibleBounds.contains(const LatLng(21.03, 105.85)), isTrue);
      expect(cam.visibleBounds.contains(const LatLng(21.10, 105.95)), isTrue);
      expect(cam.zoom, lessThan(singleResultZoom));
    });

    testMap('S5. identical coordinates fit safely (no invalid bounds)', (tester) async {
      final (controller, repo, c) = await pumpScreen(tester);
      repo.bySearch['dup'] = [place('a', 20.9, 107.0), place('b', 20.9, 107.0)];
      c.read(mapProvider.notifier).searchPlaces('dup');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(tester.takeException(), isNull);
      expect(controller.camera.center.latitude, closeTo(20.9, 1e-6));
      expect(controller.camera.zoom, singleResultZoom);
    });

    testMap('S6. zero results: truthful search empty state, camera unchanged', (tester) async {
      final (controller, _, c) = await pumpScreen(tester);
      final before = controller.camera.center;
      c.read(mapProvider.notifier).searchPlaces('zzqxwv');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      expect(find.text('Không tìm thấy địa điểm'), findsOneWidget);
      expect(find.textContaining('zzqxwv'), findsWidgets);
      expect(find.textContaining('bán kính'), findsNothing);
      expect(controller.camera.center.latitude, closeTo(before.latitude, 1e-9));
      expect(c.read(mapProvider).selectedPlace, isNull);
    });

    testMap('S7. marker tap shows the preview sheet', (tester) async {
      final (_, _, c) = await pumpScreen(tester);
      final p = c.read(mapProvider).places.first;
      c.read(mapProvider.notifier).selectPlace(p);
      await tester.pump();
      expect(find.text(p.name), findsWidgets);
    });

    testMap('S8. radius selector only in NEARBY mode', (tester) async {
      final (_, _, c) = await pumpScreen(tester);
      expect(find.text('10km'), findsNothing);
      c.read(mapProvider.notifier).setUserLocation(const LatLng(10, 106));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.text('10km'), findsOneWidget);
    });

    testMap('S9. retry in error state re-runs the current destination', (tester) async {
      tester.view.physicalSize = const Size(1200, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      final repo = seededRepo()..failOnce.add('dest:$hnId');
      await tester.pumpWidget(ProviderScope(
        overrides: [
          locationServiceProvider.overrideWithValue(FakeLocationService()),
          placeRepositoryProvider.overrideWithValue(repo),
        ],
        child: MaterialApp(theme: AppTheme.lightTheme, home: MapScreen(mapController: MapController())),
      ));
      await tester.pump(const Duration(milliseconds: 300));
      await tester.pump(const Duration(milliseconds: 300));
      expect(find.text('Thử lại'), findsOneWidget);
      await tester.tap(find.text('Thử lại'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      final c = ProviderScope.containerOf(tester.element(find.byType(MapScreen)));
      expect(c.read(mapProvider).status, MapLoadingStatus.loaded);
      expect(c.read(mapProvider).activeDestinationSlug, 'ha-noi');
    });
  });

  group('W3-05 Home lifecycle (TECH-DEBT-MOB-01)', () {
    testWidgets('T. request completing after dispose does not call setState', (tester) async {
      final completer = Completer<void>();
      final dio = Dio(BaseOptions(baseUrl: 'http://localhost'));
      dio.httpClientAdapter = _DelayedAdapter(completer.future);

      await tester.pumpWidget(ProviderScope(
        overrides: [apiClientProvider.overrideWithValue(dio)],
        child: MaterialApp(theme: AppTheme.lightTheme, home: const HomeScreen()),
      ));
      await tester.pump();
      // Leave Home while /destinations is still in flight.
      await tester.pumpWidget(const MaterialApp(home: SizedBox()));
      completer.complete();
      await tester.pump(const Duration(milliseconds: 50));
      await tester.pump();
      expect(tester.takeException(), isNull);
    });
  });
}

class _DelayedAdapter implements HttpClientAdapter {
  final Future<void> gate;
  _DelayedAdapter(this.gate);

  @override
  Future<ResponseBody> fetch(RequestOptions options,
      Stream<List<int>>? requestStream, Future<void>? cancelFuture) async {
    await gate;
    return ResponseBody.fromString(
        '{"data":{"items":[]}}', 200, headers: {
      Headers.contentTypeHeader: ['application/json']
    });
  }

  @override
  void close({bool force = false}) {}
}
