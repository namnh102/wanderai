import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/features/location/domain/geo_distance.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/map/data/place_repository.dart';
import 'package:wanderai_mobile/features/map/presentation/map_screen.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/place_preview_sheet.dart';
import 'package:wanderai_mobile/features/map/providers/map_provider.dart';
import 'package:wanderai_mobile/features/places/data/navigation_service.dart';
import 'package:wanderai_mobile/features/places/presentation/place_detail_screen.dart';

// ── Fakes ──

class FakeLocationService implements LocationService {
  LocationPermissionState permission;
  LocationPermissionState afterRequest;
  bool serviceEnabled;
  Object? error;
  LatLng position;
  int requestCalls = 0;
  int positionCalls = 0;

  FakeLocationService({
    this.permission = LocationPermissionState.denied,
    this.afterRequest = LocationPermissionState.granted,
    this.serviceEnabled = true,
    this.error,
    this.position = const LatLng(10.0, 106.0),
  });

  @override
  Future<LocationPermissionState> checkPermission() async => permission;

  @override
  Future<LocationPermissionState> requestPermission() async {
    requestCalls++;
    permission = afterRequest;
    return afterRequest;
  }

  @override
  Future<bool> isServiceEnabled() async => serviceEnabled;

  @override
  Future<LatLng> currentPosition() async {
    positionCalls++;
    if (error != null) throw error!;
    return position;
  }
}

class _MapRepo implements PlaceRepository {
  final List<PlaceModel> places;
  _MapRepo(this.places);

  @override
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10,
    int limit = 20,
    bool verifiedOnly = true,
    String? category,
  }) async =>
      places;

  @override
  Future<PlaceModel> getPlaceById(String id) async => places.first;

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

PlaceModel _place({double lat = 21.0485, double lng = 105.8363, double? serverDistance}) =>
    PlaceModel.fromJson({
      'id': 'p1',
      'name': 'Chùa Trấn Quốc',
      'latitude': lat,
      'longitude': lng,
      'rating': null,
      'reviewCount': 0,
      'category': {'name': 'culture'},
      'isVerified': true,
      'provenanceCount': 1,
      'distanceKm': serverDistance,
    });

Widget _wrap(Widget child, {List<Override> overrides = const []}) => ProviderScope(
      overrides: overrides,
      child: MaterialApp(theme: AppTheme.lightTheme, home: child),
    );

void main() {
  group('Haversine distance', () {
    test('zero for identical points, symmetric, plausible Hanoi–Hoàn Kiếm value', () {
      const a = LatLng(21.0285, 105.8542);
      const b = LatLng(21.0485, 105.8363);
      expect(haversineKm(a, a), closeTo(0, 1e-9));
      expect(haversineKm(a, b), closeTo(haversineKm(b, a), 1e-9));
      expect(haversineKm(a, b), inInclusiveRange(2.5, 3.2));
    });

    test('one degree of latitude is ~111.2 km', () {
      expect(haversineKm(const LatLng(0, 0), const LatLng(1, 0)), closeTo(111.2, 0.3));
    });

    test('unknown user or place coordinates => null (no fake distance)', () {
      expect(distanceFromUserKm(null, 21.0, 105.0), isNull);
      expect(distanceFromUserKm(const LatLng(21, 105), null, 105.0), isNull);
      expect(distanceFromUserKm(const LatLng(21, 105), 21.0, null), isNull);
      expect(distanceLabel(null), 'Khoảng cách chưa xác định');
      expect(distanceLabel(0.5), '500m');
      expect(distanceLabel(2.84), '2.8 km');
    });
  });

  group('UserLocationNotifier states', () {
    test('starts unknown with no position', () {
      final n = UserLocationNotifier(FakeLocationService());
      expect(n.state.status, UserLocationStatus.unknown);
      expect(n.state.position, isNull);
      expect(n.state.label, isNull);
    });

    test('permission granted after prompt => real position', () async {
      final svc = FakeLocationService(position: const LatLng(10.5, 106.5));
      final n = UserLocationNotifier(svc);
      final pos = await n.request();
      expect(svc.requestCalls, 1);
      expect(pos, const LatLng(10.5, 106.5));
      expect(n.state.status, UserLocationStatus.granted);
      expect(n.state.position, const LatLng(10.5, 106.5));
    });

    test('permission denied => no position, honest label', () async {
      final svc = FakeLocationService(afterRequest: LocationPermissionState.denied);
      final n = UserLocationNotifier(svc);
      expect(await n.request(), isNull);
      expect(n.state.status, UserLocationStatus.denied);
      expect(n.state.position, isNull);
      expect(n.state.label, 'Quyền vị trí bị từ chối');
      expect(svc.positionCalls, 0);
    });

    test('denied forever is not re-prompted and stays denied', () async {
      final svc = FakeLocationService(permission: LocationPermissionState.deniedForever);
      final n = UserLocationNotifier(svc);
      expect(await n.request(), isNull);
      expect(svc.requestCalls, 0);
      expect(n.state.status, UserLocationStatus.denied);
    });

    test('location service disabled => unavailable', () async {
      final svc = FakeLocationService(
          permission: LocationPermissionState.granted, serviceEnabled: false);
      final n = UserLocationNotifier(svc);
      expect(await n.request(), isNull);
      expect(n.state.status, UserLocationStatus.unavailable);
      expect(n.state.position, isNull);
      expect(n.state.label, 'Không xác định được vị trí');
    });

    test('position fetch error => unavailable, never invents a location', () async {
      final svc = FakeLocationService(
          permission: LocationPermissionState.granted, error: Exception('timeout'));
      final n = UserLocationNotifier(svc);
      expect(await n.request(), isNull);
      expect(n.state.status, UserLocationStatus.unavailable);
      expect(n.state.position, isNull);
    });

    test('requesting state is exposed while waiting', () async {
      final svc = FakeLocationService();
      final n = UserLocationNotifier(svc);
      final states = <UserLocationStatus>[];
      n.addListener(
          (s) => states.add(s.status), fireImmediately: false);
      await n.request();
      expect(states.first, UserLocationStatus.requesting);
      expect(states.last, UserLocationStatus.granted);
    });

    test('silent refresh never prompts when permission is not granted', () async {
      final svc = FakeLocationService(permission: LocationPermissionState.denied);
      final n = UserLocationNotifier(svc);
      await n.refreshIfPermitted();
      expect(svc.requestCalls, 0);
      expect(svc.positionCalls, 0);
      expect(n.state.status, UserLocationStatus.unknown);
    });

    test('silent refresh picks up a fix when already permitted', () async {
      final svc = FakeLocationService(permission: LocationPermissionState.granted);
      final n = UserLocationNotifier(svc);
      await n.refreshIfPermitted();
      expect(n.state.status, UserLocationStatus.granted);
      expect(n.state.position, const LatLng(10.0, 106.0));
    });
  });

  group('Distance display follows the real user location', () {
    testWidgets('preview: changing the user location changes the distance', (tester) async {
      final place = _place(serverDistance: 99.9);
      const near = LatLng(21.0485, 105.8463); // ~1.04 km east
      const far = LatLng(21.1485, 105.8363); // ~11.1 km north

      await tester.pumpWidget(_wrap(Scaffold(
        body: PlacePreviewSheet(
          place: place,
          onClose: () {},
          distanceKm: distanceFromUserKm(near, place.latitude, place.longitude),
        ),
      )));
      final nearKm = distanceFromUserKm(near, place.latitude, place.longitude)!;
      expect(find.text(formatDistanceKm(nearKm)), findsOneWidget);
      expect(find.text('99.9 km'), findsNothing); // server value ignored

      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(_wrap(Scaffold(
        body: PlacePreviewSheet(
          place: place,
          onClose: () {},
          distanceKm: distanceFromUserKm(far, place.latitude, place.longitude),
        ),
      )));
      final farKm = distanceFromUserKm(far, place.latitude, place.longitude)!;
      expect(farKm, greaterThan(nearKm * 5));
      expect(find.text(formatDistanceKm(farKm)), findsOneWidget);
      expect(find.text(formatDistanceKm(nearKm)), findsNothing);
    });

    testWidgets('preview: unknown location shows "Khoảng cách chưa xác định", no number', (tester) async {
      await tester.pumpWidget(_wrap(Scaffold(
        body: PlacePreviewSheet(place: _place(serverDistance: 2.8), onClose: () {}),
      )));
      expect(find.byKey(const Key('place_preview_distance')), findsOneWidget);
      expect(find.text('Khoảng cách chưa xác định'), findsOneWidget);
      expect(find.text('2.8 km'), findsNothing);
    });

    testWidgets('detail: distance shown when known, honest text when unknown', (tester) async {
      final p = _place();
      Widget view(double? km) => _wrap(Scaffold(
            body: PlaceDetailView(
                place: p, distanceKm: km, onOpenUrl: (_) {}, onDirections: () {}),
          ));

      await tester.pumpWidget(view(null));
      expect(find.text('Khoảng cách chưa xác định'), findsOneWidget);

      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(view(3.4));
      expect(find.byKey(const Key('place_detail_distance')), findsOneWidget);
      expect(find.text('3.4 km'), findsOneWidget);
      expect(find.text('Khoảng cách chưa xác định'), findsNothing);
    });

    testWidgets('detail shows the navigation hint above "Chỉ đường"', (tester) async {
      await tester.pumpWidget(_wrap(Scaffold(
        body: PlaceDetailView(
            place: _place(), onOpenUrl: (_) {}, onDirections: () {}),
      )));
      expect(find.text('Điều hướng sẽ mở ứng dụng bản đồ'), findsOneWidget);
      expect(find.text('Chỉ đường'), findsOneWidget);
    });
  });

  group('Navigation URIs', () {
    test('web/desktop: Google Directions URL with destination coordinates, no API key', () {
      for (final platform in [NavPlatform.web, NavPlatform.desktop]) {
        final uris = directionsCandidates(
            destLat: 21.0485, destLng: 105.8363, platform: platform);
        expect(uris, hasLength(1));
        final u = uris.single;
        expect(u.scheme, 'https');
        expect(u.host, 'www.google.com');
        expect(u.path, '/maps/dir/');
        expect(u.queryParameters['api'], '1');
        expect(u.queryParameters['destination'], '21.048500,105.836300');
        expect(u.queryParameters.containsKey('origin'), isFalse);
        expect(u.queryParameters.containsKey('key'), isFalse);
      }
    });

    test('origin included only when the real user location is known', () {
      final withOrigin = googleDirectionsUri(
          destLat: 21.0485, destLng: 105.8363, origin: const LatLng(21.03, 105.85));
      expect(withOrigin.queryParameters['origin'], '21.030000,105.850000');
      expect(withOrigin.queryParameters['destination'], '21.048500,105.836300');
      final without = googleDirectionsUri(destLat: 21.0485, destLng: 105.8363);
      expect(without.queryParameters.containsKey('origin'), isFalse);
    });

    test('mobile prefers native handling, with a Google fallback', () {
      final android = directionsCandidates(
          destLat: 21.0485, destLng: 105.8363, platform: NavPlatform.android);
      expect(android.first.scheme, 'geo');
      expect(android.first.toString(), contains('21.048500,105.836300'));
      expect(android.last.host, 'www.google.com');

      final ios = directionsCandidates(
          destLat: 21.0485,
          destLng: 105.8363,
          origin: const LatLng(21.03, 105.85),
          platform: NavPlatform.ios);
      expect(ios.first.host, 'maps.apple.com');
      expect(ios.first.queryParameters['daddr'], '21.048500,105.836300');
      expect(ios.first.queryParameters['saddr'], '21.030000,105.850000');
    });

    test('openDirections hands the first openable candidate to the opener', () async {
      final tried = <Uri>[];
      final opened = await openDirections(
        destLat: 21.0485,
        destLng: 105.8363,
        platform: NavPlatform.android,
        opener: (u) async {
          tried.add(u);
          return u.scheme != 'geo'; // geo unsupported -> fall back to https
        },
      );
      expect(tried.map((u) => u.scheme), ['geo', 'https']);
      expect(opened!.host, 'www.google.com');
    });

    test('openDirections returns null when nothing can be opened', () async {
      final r = await openDirections(
        destLat: 1,
        destLng: 2,
        platform: NavPlatform.web,
        opener: (_) async => false,
      );
      expect(r, isNull);
    });

    testWidgets('"Chỉ đường" button triggers the unified handler callback', (tester) async {
      var taps = 0;
      await tester.pumpWidget(_wrap(Scaffold(
        body: PlaceDetailView(
            place: _place(), onOpenUrl: (_) {}, onDirections: () => taps++),
      )));
      await tester.tap(find.byKey(const Key('place_detail_directions')));
      expect(taps, 1);
    });
  });

  group('MapScreen realtime location', () {
    Future<ProviderContainer> pumpMap(
      WidgetTester tester,
      FakeLocationService svc,
    ) async {
      tester.view.physicalSize = const Size(1200, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(_wrap(const MapScreen(), overrides: [
        locationServiceProvider.overrideWithValue(svc),
        placeRepositoryProvider.overrideWithValue(_MapRepo([_place()])),
      ]));
      await tester.pump(const Duration(milliseconds: 200));
      return ProviderScope.containerOf(tester.element(find.byType(MapScreen)));
    }

    testWidgets('initially no user marker and no fake distance; no prompt on open', (tester) async {
      final svc = FakeLocationService(permission: LocationPermissionState.denied);
      final c = await pumpMap(tester, svc);
      expect(svc.requestCalls, 0);
      expect(find.byKey(const Key('user_location_marker')), findsNothing);
      expect(find.byKey(const Key('location_status_pill')), findsNothing);
      expect(c.read(userLocationProvider).position, isNull);

      c.read(mapProvider.notifier).selectPlace(_place(serverDistance: 2.8));
      await tester.pump();
      expect(find.text('Khoảng cách chưa xác định'), findsOneWidget);
      expect(find.text('2.8 km'), findsNothing);
    });

    testWidgets('"Vị trí của tôi" granted => marker, status pill, real distance', (tester) async {
      // ~1.04 km from the place.
      final svc = FakeLocationService(position: const LatLng(21.0485, 105.8463));
      final c = await pumpMap(tester, svc);
      await tester.tap(find.byKey(const Key('my_location_button')));
      await tester.pump(const Duration(milliseconds: 200));

      expect(svc.requestCalls, 1);
      expect(find.byKey(const Key('user_location_marker')), findsOneWidget);
      expect(find.text('Đã xác định vị trí của bạn'), findsOneWidget);

      c.read(mapProvider.notifier).selectPlace(_place());
      await tester.pump();
      final km = haversineKm(const LatLng(21.0485, 105.8463), const LatLng(21.0485, 105.8363));
      expect(find.text(formatDistanceKm(km)), findsOneWidget);
    });

    testWidgets('second tap refreshes the fix (recenter action) and updates distance', (tester) async {
      final svc = FakeLocationService(position: const LatLng(21.0485, 105.8463));
      final c = await pumpMap(tester, svc);
      await tester.tap(find.byKey(const Key('my_location_button')));
      await tester.pump(const Duration(milliseconds: 200));
      c.read(mapProvider.notifier).selectPlace(_place());
      await tester.pump();
      final first = formatDistanceKm(
          haversineKm(const LatLng(21.0485, 105.8463), const LatLng(21.0485, 105.8363)));
      expect(find.text(first), findsOneWidget);

      svc.position = const LatLng(21.1485, 105.8363); // user moved ~11 km north
      await tester.tap(find.byKey(const Key('my_location_button')));
      await tester.pump(const Duration(milliseconds: 200));
      expect(svc.requestCalls, 1); // already granted: no second prompt
      expect(svc.positionCalls, 2);
      expect(c.read(userLocationProvider).position, const LatLng(21.1485, 105.8363));
      c.read(mapProvider.notifier).selectPlace(_place());
      await tester.pump();
      final second = formatDistanceKm(
          haversineKm(const LatLng(21.1485, 105.8363), const LatLng(21.0485, 105.8363)));
      expect(second, isNot(first));
      expect(find.text(second), findsOneWidget);
    });

    testWidgets('permission denied => no marker, honest message, no fake distance', (tester) async {
      final svc = FakeLocationService(afterRequest: LocationPermissionState.denied);
      final c = await pumpMap(tester, svc);
      await tester.tap(find.byKey(const Key('my_location_button')));
      await tester.pump(const Duration(milliseconds: 200));

      expect(find.byKey(const Key('user_location_marker')), findsNothing);
      expect(find.text('Quyền vị trí bị từ chối'), findsWidgets);
      c.read(mapProvider.notifier).selectPlace(_place());
      await tester.pump();
      expect(find.text('Khoảng cách chưa xác định'), findsOneWidget);
    });

    testWidgets('location unavailable => no marker, honest message', (tester) async {
      final svc = FakeLocationService(
          permission: LocationPermissionState.granted, error: Exception('no fix'));
      await pumpMap(tester, svc);
      await tester.tap(find.byKey(const Key('my_location_button')));
      await tester.pump(const Duration(milliseconds: 200));
      expect(find.byKey(const Key('user_location_marker')), findsNothing);
      expect(find.text('Không xác định được vị trí'), findsWidgets);
    });
  });

  group('MapScreen camera behaviour', () {
    const defaultCenter = LatLng(21.0285, 105.8542);
    const fixA = LatLng(10.7769, 106.7009); // far from the default centre
    const fixB = LatLng(16.0544, 108.2022);

    Future<MapController> pumpMapWithController(
      WidgetTester tester,
      FakeLocationService svc,
    ) async {
      tester.view.physicalSize = const Size(1200, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      final controller = MapController();
      await tester.pumpWidget(_wrap(
        MapScreen(mapController: controller),
        overrides: [
          locationServiceProvider.overrideWithValue(svc),
          placeRepositoryProvider.overrideWithValue(_MapRepo([_place()])),
        ],
      ));
      await tester.pump(const Duration(milliseconds: 300));
      return controller;
    }

    List<Marker> userMarkers(WidgetTester tester) => tester
        .widgetList<MarkerLayer>(find.byType(MarkerLayer))
        .expand((l) => l.markers)
        .where((m) => m.key == const Key('user_location_marker'))
        .toList();

    testWidgets('opening the map does NOT recenter, even if a fix is already available', (tester) async {
      final svc = FakeLocationService(
          permission: LocationPermissionState.granted, position: fixA);
      final controller = await pumpMapWithController(tester, svc);
      // The silent refresh found a fix and drew the marker ...
      expect(userMarkers(tester), hasLength(1));
      expect(userMarkers(tester).single.point, fixA);
      // ... but the camera stayed where it was.
      expect(controller.camera.center.latitude, closeTo(defaultCenter.latitude, 1e-6));
      expect(controller.camera.center.longitude, closeTo(defaultCenter.longitude, 1e-6));
      expect(svc.requestCalls, 0); // and no permission prompt
    });

    testWidgets('tapping "Vị trí của tôi" DOES recenter on the fix', (tester) async {
      final svc = FakeLocationService(position: fixA);
      final controller = await pumpMapWithController(tester, svc);
      expect(controller.camera.center.latitude, closeTo(defaultCenter.latitude, 1e-6));

      await tester.tap(find.byKey(const Key('my_location_button')));
      await tester.pump(const Duration(milliseconds: 300));

      expect(controller.camera.center.latitude, closeTo(fixA.latitude, 1e-6));
      expect(controller.camera.center.longitude, closeTo(fixA.longitude, 1e-6));
      expect(controller.camera.zoom, 15.0);
    });

    testWidgets('denied tap does not move the camera', (tester) async {
      final svc = FakeLocationService(afterRequest: LocationPermissionState.denied);
      final controller = await pumpMapWithController(tester, svc);
      await tester.tap(find.byKey(const Key('my_location_button')));
      await tester.pump(const Duration(milliseconds: 300));
      expect(controller.camera.center.latitude, closeTo(defaultCenter.latitude, 1e-6));
      expect(controller.camera.center.longitude, closeTo(defaultCenter.longitude, 1e-6));
    });

    testWidgets('a changed fix updates the marker; the camera moves only on tap', (tester) async {
      final svc = FakeLocationService(position: fixA);
      final c = await pumpMapWithController(tester, svc);
      await tester.tap(find.byKey(const Key('my_location_button')));
      await tester.pump(const Duration(milliseconds: 300));
      expect(userMarkers(tester).single.point, fixA);

      // The device moves; nothing happens until the user asks again.
      svc.position = fixB;
      await tester.pump(const Duration(seconds: 2));
      expect(userMarkers(tester).single.point, fixA);
      expect(c.camera.center.latitude, closeTo(fixA.latitude, 1e-6));

      await tester.tap(find.byKey(const Key('my_location_button')));
      await tester.pump(const Duration(milliseconds: 300));
      expect(userMarkers(tester), hasLength(1));
      expect(userMarkers(tester).single.point, fixB);
      expect(c.camera.center.latitude, closeTo(fixB.latitude, 1e-6));
      expect(c.camera.center.longitude, closeTo(fixB.longitude, 1e-6));
    });

    testWidgets('returning from Place Detail does NOT recenter the camera', (tester) async {
      final svc = FakeLocationService(
          permission: LocationPermissionState.granted, position: fixA);
      final controller = MapController();
      final router = GoRouter(
        initialLocation: '/map',
        routes: [
          GoRoute(path: '/map', builder: (c, _) => MapScreen(mapController: controller)),
          GoRoute(
            path: '/places/:id',
            builder: (c, s) => PlaceDetailScreen(placeId: s.pathParameters['id']!),
          ),
        ],
      );
      tester.view.physicalSize = const Size(1200, 1800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(ProviderScope(
        overrides: [
          locationServiceProvider.overrideWithValue(svc),
          placeRepositoryProvider.overrideWithValue(_MapRepo([_place()])),
        ],
        child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
      ));
      await tester.pump(const Duration(milliseconds: 300));

      // The user pans the map somewhere specific and selects a place.
      const panned = LatLng(16.0, 108.0);
      controller.move(panned, 12.0);
      await tester.pump();
      ProviderScope.containerOf(tester.element(find.byType(MapScreen)))
          .read(mapProvider.notifier)
          .selectPlace(_place());
      await tester.pump();

      router.push('/places/p1');
      await tester.pumpAndSettle();
      expect(find.byType(PlaceDetailScreen), findsOneWidget);

      router.pop();
      await tester.pumpAndSettle();
      expect(find.byType(MapScreen), findsOneWidget);
      expect(controller.camera.center.latitude, closeTo(panned.latitude, 1e-6));
      expect(controller.camera.center.longitude, closeTo(panned.longitude, 1e-6));
      expect(controller.camera.zoom, 12.0);
      expect(userMarkers(tester), hasLength(1)); // marker still drawn
    });
  });

  group('Location state machine (exact transitions)', () {
    List<UserLocationStatus> record(UserLocationNotifier n) {
      final seen = <UserLocationStatus>[n.state.status];
      n.addListener((s) => seen.add(s.status), fireImmediately: false);
      return seen;
    }

    test('unknown -> requesting -> granted', () async {
      final n = UserLocationNotifier(FakeLocationService());
      final seen = record(n);
      await n.request();
      expect(seen, [
        UserLocationStatus.unknown,
        UserLocationStatus.requesting,
        UserLocationStatus.granted,
      ]);
      expect(n.state.position, isNotNull);
    });

    test('unknown -> requesting -> denied (position stays null)', () async {
      final n = UserLocationNotifier(
          FakeLocationService(afterRequest: LocationPermissionState.denied));
      final seen = record(n);
      await n.request();
      expect(seen, [
        UserLocationStatus.unknown,
        UserLocationStatus.requesting,
        UserLocationStatus.denied,
      ]);
      expect(n.state.position, isNull);
    });

    test('unknown -> requesting -> unavailable (position stays null)', () async {
      final n = UserLocationNotifier(FakeLocationService(
          permission: LocationPermissionState.granted, serviceEnabled: false));
      final seen = record(n);
      await n.request();
      expect(seen, [
        UserLocationStatus.unknown,
        UserLocationStatus.requesting,
        UserLocationStatus.unavailable,
      ]);
      expect(n.state.position, isNull);
    });

    test('position is null until a real fix exists, including while requesting', () async {
      final n = UserLocationNotifier(FakeLocationService());
      expect(n.state.position, isNull);
      final positions = <LatLng?>[];
      n.addListener((s) => positions.add(s.position), fireImmediately: false);
      await n.request();
      expect(positions.first, isNull); // requesting
      expect(positions.last, isNotNull); // granted
    });

    test('a later denial/failure drops stale coordinates (never shown as realtime)', () async {
      final svc = FakeLocationService(position: const LatLng(10.0, 106.0));
      final n = UserLocationNotifier(svc);
      await n.request();
      expect(n.state.position, const LatLng(10.0, 106.0));

      svc.error = Exception('gps lost');
      await n.request();
      expect(n.state.status, UserLocationStatus.unavailable);
      expect(n.state.position, isNull);

      svc.error = null;
      svc.permission = LocationPermissionState.deniedForever;
      await n.request();
      expect(n.state.status, UserLocationStatus.denied);
      expect(n.state.position, isNull);
    });

    test('permission and position are separate: granted permission without a fix has no position', () async {
      final svc = FakeLocationService(permission: LocationPermissionState.granted)
        ..error = Exception('timeout');
      final n = UserLocationNotifier(svc);
      await n.request();
      expect(await svc.checkPermission(), LocationPermissionState.granted);
      expect(n.state.status, UserLocationStatus.unavailable);
      expect(n.state.position, isNull);
    });
  });

  group('Distance source and coordinate order', () {
    test('known pair: (21.03,105.85) -> Chùa Trấn Quốc (21.0479,105.83676) is about 2.42 km', () {
      final km = haversineKm(const LatLng(21.03, 105.85), const LatLng(21.0479, 105.83676));
      expect(km, closeTo(2.418, 0.02));
    });

    test('longitude is not treated as latitude: swapped pair gives a different result', () {
      final ok = haversineKm(const LatLng(21.03, 105.85), const LatLng(21.0479, 105.83676));
      final swapped = haversineKm(const LatLng(105.85, 21.03), const LatLng(105.83676, 21.0479));
      expect((ok - swapped).abs(), greaterThan(0.5));
    });

    test('distanceFromUserKm(user, placeLat, placeLng) uses (lat, lng) order', () {
      final km = distanceFromUserKm(const LatLng(21.03, 105.85), 21.0479, 105.83676)!;
      expect(km, closeTo(2.418, 0.02));
    });

    test('Google destination/origin are "lat,lng"', () {
      final u = googleDirectionsUri(
          destLat: 21.0479, destLng: 105.83676, origin: const LatLng(21.03, 105.85));
      expect(u.queryParameters['destination'], '21.047900,105.836760');
      expect(u.queryParameters['origin'], '21.030000,105.850000');
    });

    test('server distanceKm is parsed but never used for display', () {
      final p = _place(serverDistance: 99.0);
      expect(p.distanceKm, 99.0); // field kept for API compatibility
      expect(distanceFromUserKm(null, p.latitude, p.longitude), isNull);
    });
  });
}
