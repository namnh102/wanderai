import 'dart:io';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';
import 'package:wanderai_mobile/app/app.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/features/ai_chat/data/chat_models.dart';
import 'package:wanderai_mobile/features/ai_chat/data/chat_repository.dart';
import 'package:wanderai_mobile/features/ai_chat/presentation/ai_chat_screen.dart';
import 'package:wanderai_mobile/features/ai_chat/providers/chat_provider.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/map/data/place_repository.dart';
import 'package:wanderai_mobile/features/map/presentation/map_screen.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/place_preview_sheet.dart';
import 'package:wanderai_mobile/features/map/providers/map_provider.dart';
import 'package:wanderai_mobile/features/places/data/navigation_service.dart';
import 'package:wanderai_mobile/features/places/presentation/place_detail_screen.dart';

import 'location_navigation_test.dart' show FakeLocationService;

class _StubPlaceRepo implements PlaceRepository {
  final List<PlaceModel> places;
  _StubPlaceRepo(this.places);

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
  Future<List<PlaceModel>> getPlaces({
    String? destinationId,
    String? category,
    String? search,
    int page = 1,
    int limit = 20,
    bool verifiedOnly = true,
  }) async =>
      places;

  @override
  Future<PlaceModel> getPlaceById(String id) async =>
      places.firstWhere((p) => p.id == id, orElse: () => places.first);

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _StubChatRepo extends ChatRepository {
  final List<String> sources;
  _StubChatRepo(this.sources) : super(Dio());

  @override
  Future<ChatResponse> sendMessage(ChatRequest request) async {
    return ChatResponse(
      reply: 'Thông tin xác thực từ OpenStreetMap.',
      sessionId: 's_wp_ui_01',
      sources: sources,
      retrievalStatus: RetrievalStatus.ok,
    );
  }
}

PlaceModel _sampleVerifiedPlace() => PlaceModel.fromJson({
      'id': 'p1',
      'name': 'Chùa Cầu Hội An',
      'address': 'Nguyễn Thị Minh Khai, Minh An, Hội An',
      'latitude': 15.8771,
      'longitude': 108.3261,
      'rating': 4.7,
      'reviewCount': 42,
      'category': {'name': 'culture'},
      'destination': {'name': 'Đà Nẵng'},
      'isVerified': true,
      'provenanceCount': 1,
      'openingHours': 'Mo-Su 07:00-21:00',
      'website': 'https://hoianworldheritage.org.vn',
      'phone': '+84 235 3861 327',
      'source': {
        'name': 'OpenStreetMap',
        'sourceId': 'way/456789',
        'canonicalUrl': 'https://www.openstreetmap.org/way/456789',
        'license': 'ODbL 1.0',
        'attribution': '© OpenStreetMap contributors',
      },
    });

void main() {
  group('WP-UI-01.A — Android Foreground Location States (UI-F02)', () {
    test('coarse/approximate OS grant is NEVER displayed as precise even with small radius', () async {
      final t = DateTime(2026, 11, 11, 12, 0);
      final svc = FakeLocationService(
        permission: LocationPermissionState.granted,
        sequenceFixes: [
          LocationFix(
            position: const LatLng(16.0611, 108.2208),
            accuracyMeters: 12.0, // Emulator GPS mock fix can report < 50m
            timestamp: t,
            isApproximateGrant: true, // OS granted ACCESS_COARSE_LOCATION only
          ),
        ],
      );
      final notifier = UserLocationNotifier(svc, retryDelay: Duration.zero);
      final pos = await notifier.request();

      expect(pos, const LatLng(16.0611, 108.2208));
      expect(notifier.state.status, UserLocationStatus.granted);
      expect(notifier.state.quality, isNot(LocationAccuracyQuality.good));
      expect(notifier.state.quality, LocationAccuracyQuality.approximate);
      expect(notifier.state.label, 'Vị trí ước lượng');
      expect(notifier.state.label, isNot(contains('Đã xác định vị trí')));
    });

    test('coarse/approximate OS grant with 140m and 1800m reports approximate and poor honestly', () {
      final t = DateTime(2026, 11, 11, 12, 0);
      final approx140 = LocationFix(
        position: const LatLng(16.06, 108.22),
        accuracyMeters: 140.0,
        timestamp: t,
        isApproximateGrant: true,
      );
      expect(approx140.quality, LocationAccuracyQuality.approximate);
      expect(
        UserLocationState(status: UserLocationStatus.granted, fix: approx140)
            .label,
        'Vị trí ước lượng · ±140 m',
      );

      final coarse1800 = LocationFix(
        position: const LatLng(16.06, 108.22),
        accuracyMeters: 1800.0,
        timestamp: t,
        isApproximateGrant: true,
      );
      expect(coarse1800.quality, LocationAccuracyQuality.poor);
      expect(
        UserLocationState(status: UserLocationStatus.granted, fix: coarse1800)
            .label,
        'Vị trí chưa chính xác',
      );
    });

    test('precise grant (<= 50m) reports good accuracy and exact label', () async {
      final svc = FakeLocationService(
        permission: LocationPermissionState.granted,
        position: const LatLng(21.0285, 105.8542),
        accuracyMeters: 18.0,
      );
      final notifier = UserLocationNotifier(svc);
      await notifier.request();

      expect(notifier.state.status, UserLocationStatus.granted);
      expect(notifier.state.quality, LocationAccuracyQuality.good);
      expect(notifier.state.label, 'Đã xác định vị trí · ±18 m');
    });

    testWidgets('deniedForever does not re-prompt and shows permanent-denial recovery SnackBar', (tester) async {
      final svc = FakeLocationService(
        permission: LocationPermissionState.deniedForever,
      );
      tester.view.physicalSize = const Size(1080, 2400);
      tester.view.devicePixelRatio = 2.625;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            locationServiceProvider.overrideWithValue(svc),
            placeRepositoryProvider.overrideWithValue(
              _StubPlaceRepo([_sampleVerifiedPlace()]),
            ),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const MapScreen(),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 250));

      expect(svc.requestCalls, 0);
      await tester.tap(find.byKey(const Key('my_location_button')));
      await tester.pumpAndSettle();

      expect(svc.requestCalls, 0); // Must never re-prompt when deniedForever
      expect(
        find.text(
          'Quyền vị trí đã bị từ chối vĩnh viễn. Vui lòng bật trong Cài đặt.',
        ),
        findsOneWidget,
      );
      expect(find.text('Mở cài đặt'), findsOneWidget);

      await tester.tap(find.text('Mở cài đặt'));
      await tester.pump();
      expect(svc.openAppSettingsCalls, 1);
    });
  });

  group('WP-UI-01.B — External Link & Navigation Visibility + Failure Feedback (UI-F01)', () {
    test('scheme allowlist permits only https, http, geo, tel and rejects unsafe/malformed URIs', () async {
      expect(isAllowedExternalUri(Uri.parse('https://www.openstreetmap.org/way/1')), isTrue);
      expect(isAllowedExternalUri(Uri.parse('http://example.org/place')), isTrue);
      expect(isAllowedExternalUri(Uri.parse('geo:0,0?q=16.06,108.22')), isTrue);
      expect(isAllowedExternalUri(Uri.parse('tel:+842353861327')), isTrue);

      expect(isAllowedExternalUri(Uri.parse('javascript:alert(1)')), isFalse);
      expect(isAllowedExternalUri(Uri.parse('file:///etc/passwd')), isFalse);
      expect(isAllowedExternalUri(Uri.parse('intent://scan/#Intent;end')), isFalse);
      expect(isAllowedExternalUri(Uri.parse('https://')), isFalse);
      expect(isAllowedExternalUri(Uri.parse('tel:')), isFalse);

      var called = false;
      final res = await openExternalUrlString(
        'javascript:alert(1)',
        opener: (_) async {
          called = true;
          return true;
        },
      );
      expect(res, isFalse);
      expect(called, isFalse);
    });

    testWidgets('PlaceDetailScreen opens OSM source, website, phone, and directions on success without error SnackBar', (tester) async {
      final launched = <Uri>[];
      final place = _sampleVerifiedPlace();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            placeRepositoryProvider.overrideWithValue(_StubPlaceRepo([place])),
            externalUriOpenerProvider.overrideWithValue((uri) async {
              launched.add(uri);
              // Simulate Android without native geo app -> fallback to Google Maps HTTPS
              return uri.scheme != 'geo';
            }),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const PlaceDetailScreen(placeId: 'p1'),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.byKey(const Key('place_detail_website')));
      await tester.tap(find.byKey(const Key('place_detail_website')));
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.byKey(const Key('place_detail_phone')));
      await tester.tap(find.byKey(const Key('place_detail_phone')));
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.byKey(const Key('place_detail_source_url')));
      await tester.tap(find.byKey(const Key('place_detail_source_url')));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('place_detail_directions')));
      await tester.pumpAndSettle();

      expect(
        launched.map((u) => u.toString()).toList(),
        containsAll([
          'https://hoianworldheritage.org.vn',
          'tel:+842353861327',
          'https://www.openstreetmap.org/way/456789',
        ]),
      );
      expect(
        launched.last.toString(),
        contains('https://www.google.com/maps/dir/'),
      );
      expect(find.text(externalLinkOpenFailedText), findsNothing);
      expect(find.text(directionsOpenFailedText), findsNothing);
    });

    testWidgets('PlaceDetailScreen shows clear Vietnamese SnackBar when external link or Chỉ đường fails', (tester) async {
      final place = _sampleVerifiedPlace();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            placeRepositoryProvider.overrideWithValue(_StubPlaceRepo([place])),
            externalUriOpenerProvider.overrideWithValue((_) async => false),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const PlaceDetailScreen(placeId: 'p1'),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.byKey(const Key('place_detail_source_url')));
      await tester.tap(find.byKey(const Key('place_detail_source_url')));
      await tester.pumpAndSettle();
      expect(find.text(externalLinkOpenFailedText), findsOneWidget);

      await tester.tap(find.byKey(const Key('place_detail_directions')));
      await tester.pumpAndSettle();
      expect(find.text(directionsOpenFailedText), findsOneWidget);
    });

    testWidgets('AiChatScreen source chip opens citation URL on success and shows Vietnamese SnackBar on failure', (tester) async {
      final opened = <Uri>[];
      var shouldSucceed = true;
      final fakeChatRepo = _StubChatRepo([
        'https://www.openstreetmap.org/way/37933256',
      ]);

      final container = ProviderContainer(
        overrides: [
          chatRepositoryProvider.overrideWithValue(fakeChatRepo),
          externalUriOpenerProvider.overrideWithValue((uri) async {
            opened.add(uri);
            return shouldSucceed;
          }),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const AiChatScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await container.read(chatProvider.notifier).sendMessage('Chùa Cầu ở đâu?');
      await tester.pumpAndSettle();

      final chip = find.text('OpenStreetMap (way/37933256)');
      expect(chip, findsOneWidget);

      // 1. Success path
      await tester.tap(chip);
      await tester.pumpAndSettle();
      expect(opened, [Uri.parse('https://www.openstreetmap.org/way/37933256')]);
      expect(find.text(citationLinkOpenFailedText), findsNothing);

      // 2. Failure path -> clear Vietnamese SnackBar
      shouldSucceed = false;
      await tester.tap(chip);
      await tester.pumpAndSettle();
      expect(find.text(citationLinkOpenFailedText), findsOneWidget);
    });
  });

  group('WP-UI-01.C — Map Overlay Safety: SnackBar Never Occludes PlacePreviewSheet (UI-F02)', () {
    for (final viewport in const [
      Size(1080, 2400), // Pixel 7 (411 x 914 logical @ 2.625)
      Size(945, 1680), // Compact 360 x 640 logical @ 2.625
    ]) {
      testWidgets(
        'Order 1 (select place -> GPS fails) & Order 2 (GPS fails -> select place) keep Xem chi tiết unobstructed at $viewport',
        (tester) async {
          tester.view.physicalSize = viewport;
          tester.view.devicePixelRatio = 2.625;
          addTearDown(tester.view.reset);

          final svc = FakeLocationService(
            permission: LocationPermissionState.granted,
            serviceEnabled: false, // GPS disabled -> triggers unavailable SnackBar
          );
          final mapController = MapController();
          final place = _sampleVerifiedPlace();
          var detailPushedCount = 0;

          final router = GoRouter(
            initialLocation: '/map',
            routes: [
              GoRoute(
                path: '/map',
                builder: (_, __) => MapScreen(mapController: mapController),
              ),
              GoRoute(
                path: '/places/:id',
                builder: (ctx, st) {
                  detailPushedCount++;
                  return Scaffold(
                    appBar: AppBar(
                      leading: IconButton(
                        key: const Key('back_to_map'),
                        icon: const Icon(Icons.arrow_back),
                        onPressed: () => ctx.pop(),
                      ),
                    ),
                    body: Text('DETAIL_${st.pathParameters['id']}'),
                  );
                },
              ),
            ],
          );

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                locationServiceProvider.overrideWithValue(svc),
                placeRepositoryProvider.overrideWithValue(_StubPlaceRepo([place])),
              ],
              child: MaterialApp.router(
                theme: AppTheme.lightTheme,
                routerConfig: router,
              ),
            ),
          );
          await tester.pump(const Duration(milliseconds: 300));

          final container =
              ProviderScope.containerOf(tester.element(find.byType(MapScreen)));

          // Set custom camera, category filter, and selected marker
          const customCenter = LatLng(15.8800, 108.3300);
          container.read(mapProvider.notifier).setCategory('culture');
          await tester.pump(const Duration(milliseconds: 100));
          mapController.move(customCenter, 14.5);
          container.read(mapProvider.notifier).selectPlace(place);
          await tester.pumpAndSettle();

          // ── Order 1: PlacePreviewSheet already open -> Tap GPS -> Fails ──
          await tester.tap(find.byKey(const Key('my_location_button')));
          await tester.pumpAndSettle();

          final snackFinder = find.byKey(const Key('map_location_error_snackbar'));
          final sheetFinder = find.byType(PlacePreviewSheet);
          final ctaFinder = find.byKey(const Key('place_preview_view_detail'));
          expect(snackFinder, findsOneWidget);
          expect(sheetFinder, findsOneWidget);
          expect(ctaFinder, findsOneWidget);

          final snackSurfaceFinder = find
              .descendant(
                of: snackFinder,
                matching: find.byType(Material),
              )
              .first;
          final snackRect1 = tester.getRect(snackSurfaceFinder);
          final sheetRect1 = tester.getRect(sheetFinder);
          final ctaRect1 = tester.getRect(ctaFinder);
          expect(snackRect1.overlaps(ctaRect1), isFalse);
          expect(snackRect1.bottom, lessThanOrEqualTo(sheetRect1.top));

          // Map camera, category filter, and selected marker remain intact
          expect(
            mapController.camera.center.latitude,
            closeTo(customCenter.latitude, 1e-6),
          );
          expect(
            mapController.camera.center.longitude,
            closeTo(customCenter.longitude, 1e-6),
          );
          expect(mapController.camera.zoom, closeTo(14.5, 1e-6));
          expect(container.read(mapProvider).selectedCategory, 'culture');
          expect(container.read(mapProvider).selectedPlace?.id, 'p1');

          // Real center hit-test tap on `Xem chi tiết` succeeds without SnackBar interception
          await tester.tap(ctaFinder);
          await tester.pumpAndSettle();
          expect(detailPushedCount, 1);
          expect(find.text('DETAIL_p1'), findsOneWidget);

          // Return to map; state is still preserved
          await tester.tap(find.byKey(const Key('back_to_map')));
          await tester.pumpAndSettle();
          expect(container.read(mapProvider).selectedPlace?.id, 'p1');

          // ── Order 2: Deselect -> Tap GPS (SnackBar at bottom) -> Select Place ──
          container.read(mapProvider.notifier).deselectPlace();
          await tester.pumpAndSettle();

          await tester.tap(find.byKey(const Key('my_location_button')));
          await tester.pumpAndSettle();
          expect(snackFinder, findsOneWidget);

          // Selecting a marker while SnackBar is active repositions SnackBar above sheet
          container.read(mapProvider.notifier).selectPlace(place);
          await tester.pumpAndSettle();

          final snackRect2 = tester.getRect(snackSurfaceFinder);
          final sheetRect2 = tester.getRect(sheetFinder);
          final ctaRect2 = tester.getRect(ctaFinder);
          expect(snackRect2.overlaps(ctaRect2), isFalse);
          expect(snackRect2.bottom, lessThanOrEqualTo(sheetRect2.top));

          await tester.tap(ctaFinder);
          await tester.pumpAndSettle();
          expect(detailPushedCount, 2);
        },
      );
    }
  });

  group('WP-UI-01.D — Visible App Identity & Android Platform Contracts (UI-F13)', () {
    testWidgets('WanderApp sets visible MaterialApp title to GoMate', (tester) async {
      final dummyRouter = GoRouter(
        routes: [
          GoRoute(
            path: '/',
            builder: (_, __) => const Scaffold(body: Text('HOME')),
          ),
        ],
      );
      await tester.pumpWidget(
        ProviderScope(
          overrides: [appRouterProvider.overrideWithValue(dummyRouter)],
          child: const WanderApp(),
        ),
      );
      await tester.pump();

      final materialApp = tester.widget<MaterialApp>(find.byType(MaterialApp));
      expect(materialApp.title, 'GoMate');
    });

    test('AndroidManifest.xml and build.gradle.kts enforce scoped permissions, queries, and GoMate label', () {
      final manifest =
          File('android/app/src/main/AndroidManifest.xml').readAsStringSync();
      final gradle = File('android/app/build.gradle.kts').readAsStringSync();

      // Foreground location permissions present; background & broad package query absent
      expect(manifest, contains('android.permission.ACCESS_COARSE_LOCATION'));
      expect(manifest, contains('android.permission.ACCESS_FINE_LOCATION'));
      expect(manifest, isNot(contains('ACCESS_BACKGROUND_LOCATION')));
      expect(manifest, isNot(contains('QUERY_ALL_PACKAGES')));

      // Scoped <queries> schemes
      for (final scheme in ['https', 'http', 'geo', 'tel']) {
        expect(manifest, contains('android:scheme="$scheme"'));
      }

      // Visible label is GoMate while internal applicationId/namespace stay unchanged
      expect(manifest, contains('android:label="GoMate"'));
      expect(manifest, isNot(contains('android:label="wanderai_mobile"')));
      expect(gradle, contains('namespace = "com.example.wanderai_mobile"'));
      expect(gradle, contains('applicationId = "com.example.wanderai_mobile"'));
    });
  });
}
