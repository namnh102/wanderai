import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/home/presentation/home_screen.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/places/presentation/place_detail_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_detail_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_list_screen.dart';

const _haLongDestinationId = '4eec2f30-b67d-4221-b754-8fcc7bb1160e';
const _haLongPlaceId = '0118b23e-ed95-4fc4-b26a-74b761e3eb6f';
const _haLongPlaceName = 'Cảng tàu khách quốc tế Hạ Long';
const _validAccessToken = 'jwt-access-halong';
const _validRefreshToken = 'jwt-refresh-halong';

class _PassiveLocationService implements LocationService {
  @override
  Future<LocationPermissionState> checkPermission() async =>
      LocationPermissionState.denied;

  @override
  Future<LocationPermissionState> requestPermission() async =>
      LocationPermissionState.denied;

  @override
  Future<bool> isServiceEnabled() async => true;

  @override
  Future<LocationFix> currentFix() async => LocationFix(
        position: const LatLng(20.95048, 107.05044),
        accuracyMeters: 15,
        timestamp: DateTime(2026, 11, 24, 12, 0),
      );

  @override
  Future<LatLng> currentPosition() async => const LatLng(20.95048, 107.05044);

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;
}

/// Stateful in-memory backend modeling NestJS + PostgreSQL persistence across
/// full app close & cold reopen cycles.
class _InMemoryHalongBackendAdapter implements HttpClientAdapter {
  final List<(String method, String path, String? auth)> recordedCalls = [];
  final Map<String, Map<String, dynamic>> _tripsById = {};
  int _tripSeq = 1;
  int _itemSeq = 1;

  _InMemoryHalongBackendAdapter({bool seedHaLongTrip = true}) {
    if (seedHaLongTrip) {
      _tripsById['trip-halong-001'] = {
        'id': 'trip-halong-001',
        'userId': 'user-halong-1',
        'destinationId': _haLongDestinationId,
        'destination': {
          'id': _haLongDestinationId,
          'name': 'Hạ Long',
          'slug': 'ha-long',
        },
        'title': 'Chuyến đi Hạ Long cuối tuần',
        'description': 'Khám phá di sản vịnh biển Quảng Ninh',
        'status': 'PLANNED',
        'currency': 'VND',
        'interests': <String>['nature', 'sea'],
        'itineraries': <Map<String, dynamic>>[],
      };
    }
  }

  Map<String, dynamic> get _haLongPlaceJson => {
        'id': _haLongPlaceId,
        'name': _haLongPlaceName,
        'nameEn': 'Ha Long International Cruise Port',
        'address': 'Đường Hạ Long, Bãi Cháy, Hạ Long, Quảng Ninh',
        'latitude': 20.95048,
        'longitude': 107.05044,
        'rating': 4.7,
        'reviewCount': 18,
        'isVerified': true,
        'provenanceCount': 1,
        'category': {'name': 'attraction'},
        'destination': {
          'id': _haLongDestinationId,
          'name': 'Hạ Long',
          'slug': 'ha-long',
        },
        'source': {
          'name': 'OpenStreetMap',
          'canonicalUrl': 'https://www.openstreetmap.org/way/701234567',
          'license': 'ODbL 1.0',
          'attribution': '© OpenStreetMap contributors',
        },
      };

  bool _isAuthorized(RequestOptions options) {
    final auth = options.headers['Authorization']?.toString();
    return auth == 'Bearer $_validAccessToken';
  }

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final method = options.method.toUpperCase();
    final path = options.path;
    final auth = options.headers['Authorization']?.toString();
    recordedCalls.add((method, path, auth));

    if (method == 'POST' && path == '/auth/login') {
      final data = Map<String, dynamic>.from(options.data as Map);
      if (data['email'] == 'traveler@gomate.vn' &&
          data['password'] == 'Secret123!') {
        return _json(200, {
          'success': true,
          'data': {
            'access_token': _validAccessToken,
            'refresh_token': _validRefreshToken,
          },
        });
      }
      return _json(401, {'message': 'Sai thông tin đăng nhập'});
    }

    if (method == 'POST' && path == '/auth/logout') {
      return _json(200, {'success': true, 'data': {}});
    }

    if (method == 'GET' && path == '/destinations') {
      return _json(200, {
        'success': true,
        'data': {
          'items': [
            {
              'id': _haLongDestinationId,
              'name': 'Hạ Long',
              'slug': 'ha-long',
              'province': 'Quảng Ninh',
              'region': 'north',
              'description': 'Kỳ quan thiên nhiên thế giới Vịnh Hạ Long.',
              'rating': 4.8,
              'reviewCount': 42,
              'isPopular': true,
              '_count': {'places': 64},
            },
          ],
        },
      });
    }

    if (method == 'GET' && path == '/places') {
      return _json(200, {
        'success': true,
        'data': {
          'items': [_haLongPlaceJson],
        },
      });
    }

    if (method == 'GET' && path == '/places/$_haLongPlaceId') {
      return _json(200, {
        'success': true,
        'data': _haLongPlaceJson,
      });
    }

    if (method == 'GET' && path == '/users/me') {
      if (!_isAuthorized(options)) {
        return _json(401, {'message': 'Unauthorized'});
      }
      return _json(200, {
        'success': true,
        'data': {
          'id': 'user-halong-1',
          'email': 'traveler@gomate.vn',
          'profile': {'displayName': 'Hải Nam'},
          'preferences': {
            'interests': ['nature'],
          },
        },
      });
    }

    if (method == 'GET' && path == '/trips') {
      if (!_isAuthorized(options)) {
        return _json(401, {'message': 'Unauthorized'});
      }
      return _json(200, {
        'success': true,
        'data': _tripsById.values.toList(),
      });
    }

    if (method == 'POST' && path == '/trips') {
      if (!_isAuthorized(options)) {
        return _json(401, {'message': 'Unauthorized'});
      }
      final body = Map<String, dynamic>.from(options.data as Map);
      final id = 'trip-created-${_tripSeq++}';
      final created = <String, dynamic>{
        'id': id,
        'userId': 'user-halong-1',
        'destinationId': body['destinationId'],
        'destination': body['destinationId'] == _haLongDestinationId
            ? {
                'id': _haLongDestinationId,
                'name': 'Hạ Long',
                'slug': 'ha-long',
              }
            : null,
        'title': body['title'] as String,
        'description': body['description'],
        'status': 'DRAFT',
        'currency': 'VND',
        'interests': <String>[],
        'itineraries': <Map<String, dynamic>>[],
      };
      _tripsById[id] = created;
      return _json(201, {'success': true, 'data': created});
    }

    final tripDetailMatch = RegExp(r'^/trips/([^/]+)$').firstMatch(path);
    if (method == 'GET' && tripDetailMatch != null) {
      if (!_isAuthorized(options)) {
        return _json(401, {'message': 'Unauthorized'});
      }
      final tripId = tripDetailMatch.group(1)!;
      final trip = _tripsById[tripId];
      if (trip == null) {
        return _json(404, {'message': 'Trip not found'});
      }
      return _json(200, {'success': true, 'data': trip});
    }

    final addItinMatch = RegExp(r'^/trips/([^/]+)/itinerary$').firstMatch(path);
    if (method == 'POST' && addItinMatch != null) {
      if (!_isAuthorized(options)) {
        return _json(401, {'message': 'Unauthorized'});
      }
      final tripId = addItinMatch.group(1)!;
      final trip = _tripsById[tripId];
      if (trip == null) {
        return _json(404, {'message': 'Trip not found'});
      }
      final body = Map<String, dynamic>.from(options.data as Map);
      final dayNum = body['dayNumber'] as int;
      final itineraries =
          (trip['itineraries'] as List).cast<Map<String, dynamic>>();
      var dayEntry = itineraries
          .where((d) => d['dayNumber'] == dayNum)
          .cast<Map<String, dynamic>?>()
          .firstWhere((d) => d != null, orElse: () => null);
      if (dayEntry == null) {
        dayEntry = {
          'id': 'itin-day-$dayNum',
          'dayNumber': dayNum,
          'title': 'Ngày $dayNum',
          'items': <Map<String, dynamic>>[],
        };
        itineraries.add(dayEntry);
      }
      final items = (dayEntry['items'] as List).cast<Map<String, dynamic>>();
      final placeId = body['placeId'] as String?;
      final newItem = <String, dynamic>{
        'id': 'itin-item-${_itemSeq++}',
        'orderIndex': items.length + 1,
        'activity': body['activity'] as String,
        'placeId': placeId,
        'notes': body['notes'],
        if (placeId == _haLongPlaceId)
          'place': {
            'id': _haLongPlaceId,
            'name': _haLongPlaceName,
            'address': 'Đường Hạ Long, Bãi Cháy, Hạ Long, Quảng Ninh',
          },
      };
      items.add(newItem);
      return _json(201, {'success': true, 'data': newItem});
    }

    return _json(404, {'message': 'Unhandled route $method $path'});
  }

  ResponseBody _json(int statusCode, Map<String, dynamic> payload) {
    return ResponseBody.fromString(
      jsonEncode(payload),
      statusCode,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

ProviderContainer _createAppContainer(_InMemoryHalongBackendAdapter backend) {
  return ProviderContainer(
    overrides: [
      locationServiceProvider.overrideWithValue(_PassiveLocationService()),
      apiClientProvider.overrideWith((ref) {
        final epoch = ref.read(sessionEpochControllerProvider);
        return createApiClient(
          baseUrlOverride: 'http://localhost:3000/api/v1',
          sessionEpoch: epoch,
          onSessionExpired: () {
            ref.read(authSessionExpiredSignalProvider.notifier).state++;
          },
        )..httpClientAdapter = backend;
      }),
    ],
  );
}

Future<void> _pumpFrames(WidgetTester tester, [int count = 4]) async {
  for (var i = 0; i < count; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
}

void main() {
  group('Redirect sanitizer & PlaceDetail CTA layout', () {
    test(
        'sanitizeInternalRedirect accepts internal paths and rejects open redirects',
        () {
      expect(
        sanitizeInternalRedirect('/places/$_haLongPlaceId'),
        '/places/$_haLongPlaceId',
      );
      expect(sanitizeInternalRedirect('/trips/trip-halong-001'),
          '/trips/trip-halong-001');
      expect(sanitizeInternalRedirect('https://evil.example/phish'), isNull);
      expect(sanitizeInternalRedirect('//evil.example/phish'), isNull);
      expect(sanitizeInternalRedirect('javascript:alert(1)'), isNull);
      expect(sanitizeInternalRedirect('/login'), isNull);
      expect(sanitizeInternalRedirect('/register'), isNull);
      expect(sanitizeInternalRedirect(''), isNull);
      expect(sanitizeInternalRedirect(null), isNull);
    });

    testWidgets(
        'PlaceDetailView with onSaveToTrip has zero overflow at 360x800 @ 1.3x',
        (tester) async {
      tester.view.physicalSize = const Size(360, 800);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final place = PlaceModel.fromJson({
        'id': _haLongPlaceId,
        'name': _haLongPlaceName,
        'address': 'Đường Hạ Long, Bãi Cháy, Hạ Long, Quảng Ninh',
        'latitude': 20.95048,
        'longitude': 107.05044,
        'isVerified': true,
        'category': {'name': 'attraction'},
        'destination': {
          'id': _haLongDestinationId,
          'name': 'Hạ Long',
        },
      });

      await tester.pumpWidget(
        ProviderScope(
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: MediaQuery(
              data: const MediaQueryData(textScaler: TextScaler.linear(1.3)),
              child: Scaffold(
                body: PlaceDetailView(
                  place: place,
                  onOpenUrl: (_) {},
                  onDirections: () {},
                  onAskWandy: () {},
                  onSaveToTrip: () {},
                ),
              ),
            ),
          ),
        ),
      );
      await _pumpFrames(tester);
      expect(
          find.byKey(const Key('place_detail_save_to_trip')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('Hạ Long POI -> Trip Save Journeys', () {
    testWidgets(
      'Case 1: Khám phá Hạ Long -> mở chi tiết POI -> chọn chuyến -> lưu -> đóng và mở lại app -> mở chuyến vừa chọn',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        SharedPreferences.setMockInitialValues({
          'access_token': _validAccessToken,
          'refresh_token': _validRefreshToken,
        });
        final backend = _InMemoryHalongBackendAdapter(seedHaLongTrip: true);

        // ── SESSION 1: Launch logged-in app ──
        final container1 = _createAppContainer(backend);
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container1,
            child: MaterialApp.router(
              theme: AppTheme.lightTheme,
              routerConfig: container1.read(appRouterProvider),
            ),
          ),
        );
        await _pumpFrames(tester, 6);

        expect(find.byType(HomeScreen), findsOneWidget);
        expect(find.text('Xin chào, Hải Nam 👋'), findsOneWidget);

        // 1. Khám phá Hạ Long
        final haLongCard = find.byKey(const Key('home_dest_ha-long'));
        await tester.ensureVisible(haLongCard);
        await _pumpFrames(tester, 2);
        await tester.tap(haLongCard);
        await _pumpFrames(tester, 6);

        expect(find.text('Mở trên Bản đồ'), findsOneWidget);
        expect(find.text(_haLongPlaceName), findsWidgets);

        // 2. Mở chi tiết POI từ DestinationPlacesSheet
        final sheetPoiTile = find.descendant(
          of: find.byType(BottomSheet),
          matching: find.text(_haLongPlaceName),
        );
        expect(sheetPoiTile, findsOneWidget);
        await tester.tap(sheetPoiTile);
        await _pumpFrames(tester, 6);

        expect(find.byType(PlaceDetailScreen), findsOneWidget);
        expect(
          container1
              .read(appRouterProvider)
              .routerDelegate
              .currentConfiguration
              .last
              .matchedLocation,
          '/places/$_haLongPlaceId',
        );

        // 3. Chọn chuyến -> Lưu
        await tester.tap(find.byKey(const Key('place_detail_save_to_trip')));
        await _pumpFrames(tester, 6);

        expect(
            find.byKey(const Key('save_place_to_trip_sheet')), findsOneWidget);
        final tripOption =
            find.byKey(const Key('trip_picker_item_trip-halong-001'));
        expect(tripOption, findsOneWidget);
        await tester.tap(tripOption);
        await _pumpFrames(tester, 2);

        await tester.tap(find.byKey(const Key('trip_picker_confirm_save')));
        await _pumpFrames(tester, 6);

        expect(
          backend.recordedCalls.any(
            (c) =>
                c.$1 == 'POST' &&
                c.$2 == '/trips/trip-halong-001/itinerary' &&
                c.$3 == 'Bearer $_validAccessToken',
          ),
          isTrue,
        );
        expect(
          find.textContaining('Đã lưu "$_haLongPlaceName"'),
          findsOneWidget,
        );

        // 4. Đóng toàn bộ app (hủy cây widget + dispose toàn bộ Riverpod state trong RAM)
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump();
        container1.dispose();

        final prefsAfterClose = await SharedPreferences.getInstance();
        expect(prefsAfterClose.getString('access_token'), _validAccessToken);

        // 5. Mở lại app từ đầu (ProviderContainer + GoRouter hoàn toàn mới, đọc lại từ SharedPreferences + Backend)
        final container2 = _createAppContainer(backend);
        addTearDown(container2.dispose);

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container2,
            child: MaterialApp.router(
              theme: AppTheme.lightTheme,
              routerConfig: container2.read(appRouterProvider),
            ),
          ),
        );
        await _pumpFrames(tester, 6);

        expect(container2.read(authProvider).status, AuthStatus.authenticated);
        expect(find.byType(HomeScreen), findsOneWidget);

        // 6. Mở tab "Chuyến đi" -> mở chuyến vừa chọn
        await tester.tap(find.text('Chuyến đi'));
        await _pumpFrames(tester, 6);
        expect(find.byType(TripListScreen), findsOneWidget);

        final savedTripCard =
            find.byKey(const Key('trip_card_trip-halong-001'));
        expect(savedTripCard, findsOneWidget);
        await tester.tap(savedTripCard);
        await _pumpFrames(tester, 6);

        expect(find.byType(TripDetailScreen), findsOneWidget);

        // Cuộn tới phần lịch trình chi tiết và xác minh POI Hạ Long vẫn còn nguyên sau khi mở lại app
        final savedActivity = find.text('Tham quan $_haLongPlaceName');
        await tester.scrollUntilVisible(
          savedActivity,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await _pumpFrames(tester, 2);

        expect(savedActivity, findsOneWidget);
        expect(
          find.byKey(const Key('trip_item_place_$_haLongPlaceId')),
          findsOneWidget,
        );

        // Nhấn vào mục POI đã lưu trong chuyến đi để mở lại đúng chi tiết POI
        await tester
            .tap(find.byKey(const Key('trip_itinerary_item_itin-item-1')));
        await _pumpFrames(tester, 6);
        expect(find.byType(PlaceDetailScreen), findsOneWidget);
        expect(
          container2
              .read(appRouterProvider)
              .routerDelegate
              .currentConfiguration
              .last
              .matchedLocation,
          '/places/$_haLongPlaceId',
        );
      },
    );

    testWidgets(
      'Case 2: Chưa đăng nhập bấm lưu tại POI -> chuyển sang Đăng nhập -> đăng nhập xong quay về đúng POI và lưu thành công',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        SharedPreferences.setMockInitialValues({});
        final backend = _InMemoryHalongBackendAdapter(seedHaLongTrip: false);
        final container = _createAppContainer(backend);
        addTearDown(container.dispose);

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp.router(
              theme: AppTheme.lightTheme,
              routerConfig: container.read(appRouterProvider),
            ),
          ),
        );
        await _pumpFrames(tester, 6);

        // Cold start khi chưa đăng nhập vào màn Login và không gọi /users/me
        expect(container.read(authProvider).status, AuthStatus.unauthenticated);
        expect(find.byKey(const Key('login_guest_explore_button')),
            findsOneWidget);
        expect(
          backend.recordedCalls.where((c) => c.$2 == '/users/me'),
          isEmpty,
        );

        // Chọn khám phá trước khi đăng nhập -> mở Hạ Long -> mở chi tiết POI
        await tester.tap(find.byKey(const Key('login_guest_explore_button')));
        await _pumpFrames(tester, 6);
        expect(find.byType(HomeScreen), findsOneWidget);
        expect(
          backend.recordedCalls.where((c) => c.$2 == '/users/me'),
          isEmpty,
        );

        final haLongCard = find.byKey(const Key('home_dest_ha-long'));
        await tester.ensureVisible(haLongCard);
        await _pumpFrames(tester, 2);
        await tester.tap(haLongCard);
        await _pumpFrames(tester, 6);

        final guestSheetPoiTile = find.descendant(
          of: find.byType(BottomSheet),
          matching: find.text(_haLongPlaceName),
        );
        expect(guestSheetPoiTile, findsOneWidget);
        await tester.tap(guestSheetPoiTile);
        await _pumpFrames(tester, 6);
        expect(find.byType(PlaceDetailScreen), findsOneWidget);

        // Bấm Lưu khi chưa đăng nhập -> chuyển tới /login?redirect=%2Fplaces%2F<id>
        await tester.tap(find.byKey(const Key('place_detail_save_to_trip')));
        await _pumpFrames(tester, 6);

        final loginUri = container
            .read(appRouterProvider)
            .routeInformationProvider
            .value
            .uri;
        expect(loginUri.path, '/login');
        expect(loginUri.queryParameters['redirect'], '/places/$_haLongPlaceId');
        expect(find.byKey(const Key('login_redirect_notice')), findsOneWidget);

        // Đăng nhập -> GoRouter tự động trả về đúng POI vừa xem (không đẩy về '/')
        await tester.enterText(
          find.byKey(const Key('login_email_input')),
          'traveler@gomate.vn',
        );
        await tester.enterText(
          find.byKey(const Key('login_password_input')),
          'Secret123!',
        );
        await tester.tap(find.byKey(const Key('login_submit_button')));
        await _pumpFrames(tester, 8);

        expect(container.read(authProvider).status, AuthStatus.authenticated);
        final postLoginUri = container
            .read(appRouterProvider)
            .routeInformationProvider
            .value
            .uri;
        expect(postLoginUri.path, '/places/$_haLongPlaceId');
        expect(find.byType(PlaceDetailScreen), findsOneWidget);
        expect(find.text(_haLongPlaceName), findsOneWidget);

        // Sau khi quay về đúng POI, người dùng tạo chuyến mới ngay trong sheet và lưu thành công
        await tester.tap(find.byKey(const Key('place_detail_save_to_trip')));
        await _pumpFrames(tester, 6);

        expect(
            find.byKey(const Key('save_place_to_trip_sheet')), findsOneWidget);
        expect(find.byKey(const Key('trip_picker_new_title_input')),
            findsOneWidget);

        await tester.tap(find.byKey(const Key('trip_picker_confirm_save')));
        await _pumpFrames(tester, 6);

        expect(
          backend.recordedCalls.any(
            (c) => c.$1 == 'POST' && c.$2 == '/trips',
          ),
          isTrue,
        );
        expect(
          backend.recordedCalls.any(
            (c) => c.$1 == 'POST' && c.$2 == '/trips/trip-created-1/itinerary',
          ),
          isTrue,
        );
        expect(
          find.textContaining('Đã lưu "$_haLongPlaceName"'),
          findsOneWidget,
        );
      },
    );
  });
}
