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
import 'package:wanderai_mobile/features/trips/providers/trip_provider.dart';

const _haLongDestinationId = '4eec2f30-b67d-4221-b754-8fcc7bb1160e';
const _clockTowerPlaceId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
const _clockTowerPlaceName = 'Tháp Đồng Hồ';
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
        position: const LatLng(20.95125, 107.08190),
        accuracyMeters: 15,
        timestamp: DateTime(2026, 11, 25, 1, 45),
      );

  @override
  Future<LatLng> currentPosition() async => const LatLng(20.95125, 107.08190);

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;
}

/// Stateful in-memory backend modeling NestJS + PostgreSQL behavior:
/// - 25 verified Hạ Long POIs sorted by id where `65562a67-...` (Tháp Đồng Hồ)
///   sits beyond page-1 `limit: 20` unless `search` is used.
/// - Optional `failAddItineraryTimes` to simulate transient failure after
///   `POST /trips` succeeds.
class _InMemoryHalongBackendAdapter implements HttpClientAdapter {
  final List<(String method, String path, String? auth)> recordedCalls = [];
  final Map<String, Map<String, dynamic>> _tripsById = {};
  int failAddItineraryRemaining;
  int _tripSeq = 1;
  int _itemSeq = 1;

  _InMemoryHalongBackendAdapter({
    bool seedHaLongTrip = true,
    this.failAddItineraryRemaining = 0,
  }) {
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
        'interests': <String>['nature', 'culture'],
        'itineraries': <Map<String, dynamic>>[],
      };
    }
  }

  int get createTripCallCount =>
      recordedCalls.where((c) => c.$1 == 'POST' && c.$2 == '/trips').length;

  Map<String, dynamic> get _clockTowerPlaceJson => {
        'id': _clockTowerPlaceId,
        'name': _clockTowerPlaceName,
        'address': null,
        'latitude': 20.95125,
        'longitude': 107.08190,
        'rating': null,
        'reviewCount': 0,
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
          'canonicalUrl': 'https://www.openstreetmap.org/node/123456789',
          'license': 'ODbL 1.0',
          'attribution': '© OpenStreetMap contributors',
        },
      };

  List<Map<String, dynamic>> get _allHaLongPlaces {
    final prefixPlaces = List.generate(
      22,
      (idx) => <String, dynamic>{
        'id': '00000000-0000-4000-8000-${idx.toString().padLeft(12, '0')}',
        'name': 'Địa điểm Hạ Long #${idx + 1}',
        'address': 'Hạ Long, Quảng Ninh',
        'latitude': 20.95 + idx * 0.001,
        'longitude': 107.05 + idx * 0.001,
        'rating': null,
        'reviewCount': 0,
        'isVerified': true,
        'provenanceCount': 1,
        'category': {'name': 'attraction'},
        'destination': {
          'id': _haLongDestinationId,
          'name': 'Hạ Long',
          'slug': 'ha-long',
        },
      },
    );
    return [...prefixPlaces, _clockTowerPlaceJson];
  }

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
              '_count': {'places': 197},
            },
          ],
        },
      });
    }

    if (method == 'GET' && path == '/places') {
      final search =
          (options.queryParameters['search']?.toString() ?? '').trim();
      final limit =
          int.tryParse(options.queryParameters['limit']?.toString() ?? '') ??
              20;
      var filtered = _allHaLongPlaces;
      if (search.isNotEmpty) {
        filtered = filtered
            .where(
              (p) => (p['name'] as String)
                  .toLowerCase()
                  .contains(search.toLowerCase()),
            )
            .toList();
      }
      return _json(200, {
        'success': true,
        'data': {
          'items': filtered.take(limit).toList(),
          'total': filtered.length,
        },
      });
    }

    if (method == 'GET' && path == '/places/$_clockTowerPlaceId') {
      return _json(200, {
        'success': true,
        'data': _clockTowerPlaceJson,
      });
    }

    if (method == 'GET' && path == '/places/trending') {
      return _json(200, {
        'success': true,
        'data': _allHaLongPlaces.take(5).toList(),
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
      if (failAddItineraryRemaining > 0) {
        failAddItineraryRemaining--;
        return _json(503, {
          'message':
              'Máy chủ tạm thời gián đoạn khi thêm địa điểm vào lịch trình.',
        });
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
        if (placeId == _clockTowerPlaceId)
          'place': {
            'id': _clockTowerPlaceId,
            'name': _clockTowerPlaceName,
            'address': null,
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
          baseUrlOverride: 'http://localhost:3000',
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
          sanitizeInternalRedirect('/places/$_clockTowerPlaceId'),
          '/places/$_clockTowerPlaceId',
        );
        expect(
          sanitizeInternalRedirect('/trips/trip-halong-001'),
          '/trips/trip-halong-001',
        );
        expect(sanitizeInternalRedirect('https://evil.example/phish'), isNull);
        expect(sanitizeInternalRedirect('//evil.example/phish'), isNull);
        expect(sanitizeInternalRedirect('javascript:alert(1)'), isNull);
        expect(sanitizeInternalRedirect('/login'), isNull);
        expect(sanitizeInternalRedirect('/register'), isNull);
        expect(sanitizeInternalRedirect(''), isNull);
        expect(sanitizeInternalRedirect(null), isNull);
      },
    );

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
          'id': _clockTowerPlaceId,
          'name': _clockTowerPlaceName,
          'latitude': 20.95125,
          'longitude': 107.08190,
          'rating': 4.6,
          'reviewCount': 9,
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
                    onWriteReview: () {},
                    onSaveToTrip: () {},
                  ),
                ),
              ),
            ),
          ),
        );
        await _pumpFrames(tester);
        expect(
          find.byKey(const Key('place_detail_save_to_trip')),
          findsOneWidget,
        );
        expect(tester.takeException(), isNull);
      },
    );
  });

  group('Hạ Long Tháp Đồng Hồ (65562a67-...) -> Trip Save & Retry Journeys',
      () {
    testWidgets(
      'Retry guard: createTrip succeeds -> addItineraryItem fails -> retry reuses created trip.id (POST /trips called once) and saves exact POI',
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
        final backend = _InMemoryHalongBackendAdapter(
          seedHaLongTrip: false,
          failAddItineraryRemaining: 1,
        );
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

        // Điều hướng tới chi tiết Tháp Đồng Hồ
        container.read(appRouterProvider).push('/places/$_clockTowerPlaceId');
        await _pumpFrames(tester, 6);
        expect(find.byType(PlaceDetailScreen), findsOneWidget);
        expect(find.text(_clockTowerPlaceName), findsOneWidget);

        // Mở sheet Lưu vào chuyến đi (chưa có chuyến nào -> chế độ tạo chuyến mới)
        await tester.tap(find.byKey(const Key('place_detail_save_to_trip')));
        await _pumpFrames(tester, 6);
        expect(
          find.byKey(const Key('trip_picker_new_title_input')),
          findsOneWidget,
        );

        await tester.enterText(
          find.byKey(const Key('trip_picker_new_title_input')),
          'Chuyến Hạ Long Retry 1 Lần',
        );
        await _pumpFrames(tester, 2);

        // Lần bấm 1: POST /trips thành công (tạo trip-created-1), nhưng POST /trips/trip-created-1/itinerary lỗi 503
        await tester.tap(find.byKey(const Key('trip_picker_confirm_save')));
        await _pumpFrames(tester, 6);

        expect(backend.createTripCallCount, 1);
        expect(
          find.byKey(const Key('save_place_to_trip_sheet')),
          findsOneWidget,
        );
        expect(
          find.textContaining('tạm thời gián đoạn'),
          findsOneWidget,
        );
        // Sheet phải chuyển sang giữ chọn đúng chuyến vừa tạo (trip-created-1), không còn ở form tạo mới
        expect(
          find.byKey(const Key('trip_picker_item_trip-created-1')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('trip_picker_new_title_input')),
          findsNothing,
        );

        // Lần bấm thử lại (Retry): KHÔNG gọi POST /trips lần 2, dùng đúng trip-created-1 và lưu đúng Tháp Đồng Hồ
        await tester.tap(find.byKey(const Key('trip_picker_confirm_save')));
        await _pumpFrames(tester, 6);

        expect(
          backend.createTripCallCount,
          1,
          reason:
              'Retry must reuse created trip.id and never duplicate POST /trips',
        );
        final addItineraryCalls = backend.recordedCalls
            .where(
              (c) =>
                  c.$1 == 'POST' && c.$2 == '/trips/trip-created-1/itinerary',
            )
            .toList();
        expect(addItineraryCalls, hasLength(2));
        expect(
          find.textContaining(
              'Đã lưu "$_clockTowerPlaceName" vào "Chuyến Hạ Long Retry 1 Lần"'),
          findsOneWidget,
        );

        // Kiểm tra chỉ tồn tại duy nhất 1 chuyến (trip-created-1) và chứa đúng place_id Tháp Đồng Hồ
        final savedTrips = container.read(tripListProvider).trips;
        expect(savedTrips, hasLength(1));
        expect(savedTrips.single.id, 'trip-created-1');

        container.read(appRouterProvider).push('/trips/trip-created-1');
        await _pumpFrames(tester, 6);
        final detail = container.read(tripDetailProvider).trip!;
        expect(
          detail.itineraries.single.items.single.placeId,
          _clockTowerPlaceId,
        );
      },
    );

    testWidgets(
      'Case 1: Khám phá Hạ Long -> tìm Tháp Đồng Hồ trong giao diện -> mở chi tiết -> lưu vào chuyến -> đóng hẳn app -> mở lại -> mở chuyến',
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

        // ── SESSION 1: Mở app -> Khám phá Hạ Long ──
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

        // 1. Nhấn thẻ Khám phá Hạ Long
        final haLongCard = find.byKey(const Key('home_dest_ha-long'));
        await tester.ensureVisible(haLongCard);
        await _pumpFrames(tester, 2);
        await tester.tap(haLongCard);
        await _pumpFrames(tester, 6);

        // Mặc định trang 1 (20 mục đầu) chưa chứa Tháp Đồng Hồ (nằm ngoài top 20)
        expect(
          find.byKey(const Key('dest_place_tile_$_clockTowerPlaceId')),
          findsNothing,
        );

        // 2. Tìm "Tháp Đồng Hồ" ngay trong thanh tìm kiếm của DestinationPlacesSheet
        final destSearchInput = find.descendant(
          of: find.byKey(const Key('destination_places_search_bar')),
          matching: find.byType(TextField),
        );
        expect(destSearchInput, findsOneWidget);
        await tester.enterText(destSearchInput, _clockTowerPlaceName);
        await tester.pump(const Duration(milliseconds: 350));
        await _pumpFrames(tester, 6);

        final clockTowerTile =
            find.byKey(const Key('dest_place_tile_$_clockTowerPlaceId'));
        expect(clockTowerTile, findsOneWidget);

        // 3. Mở chi tiết Tháp Đồng Hồ
        await tester.tap(clockTowerTile);
        await _pumpFrames(tester, 6);

        expect(find.byType(PlaceDetailScreen), findsOneWidget);
        expect(
          container1
              .read(appRouterProvider)
              .routerDelegate
              .currentConfiguration
              .last
              .matchedLocation,
          '/places/$_clockTowerPlaceId',
        );

        // 4. Chọn chuyến -> Lưu
        await tester.tap(find.byKey(const Key('place_detail_save_to_trip')));
        await _pumpFrames(tester, 6);

        final tripOption =
            find.byKey(const Key('trip_picker_item_trip-halong-001'));
        expect(tripOption, findsOneWidget);
        await tester.tap(tripOption);
        await _pumpFrames(tester, 2);

        await tester.tap(find.byKey(const Key('trip_picker_confirm_save')));
        await _pumpFrames(tester, 6);

        expect(
          find.textContaining('Đã lưu "$_clockTowerPlaceName"'),
          findsOneWidget,
        );

        // 5. Đóng hẳn app (unmount toàn bộ widget tree + dispose ProviderContainer)
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump();
        container1.dispose();

        // 6. Mở lại app từ đầu -> mở tab Chuyến đi -> mở chuyến vừa lưu
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
        await tester.tap(find.text('Chuyến đi'));
        await _pumpFrames(tester, 6);
        expect(find.byType(TripListScreen), findsOneWidget);

        await tester.tap(find.byKey(const Key('trip_card_trip-halong-001')));
        await _pumpFrames(tester, 6);
        expect(find.byType(TripDetailScreen), findsOneWidget);

        final savedActivity = find.text('Tham quan $_clockTowerPlaceName');
        await tester.scrollUntilVisible(
          savedActivity,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await _pumpFrames(tester, 2);

        expect(savedActivity, findsOneWidget);
        expect(
          find.byKey(const Key('trip_item_place_$_clockTowerPlaceId')),
          findsOneWidget,
        );

        // Chạm mục đã lưu mở lại đúng chi tiết Tháp Đồng Hồ
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
          '/places/$_clockTowerPlaceId',
        );
      },
    );

    testWidgets(
      'Case 2: Chưa đăng nhập bấm lưu tại Tháp Đồng Hồ -> chuyển sang Đăng nhập -> đăng nhập xong quay về đúng Tháp Đồng Hồ và lưu thành công',
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

        expect(
          container.read(authProvider).status,
          AuthStatus.unauthenticated,
        );
        expect(
          backend.recordedCalls.where((c) => c.$2 == '/users/me'),
          isEmpty,
        );

        // Khách bấm Khám phá trước khi đăng nhập -> Khám phá Hạ Long -> tìm Tháp Đồng Hồ
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

        final destSearchInput = find.descendant(
          of: find.byKey(const Key('destination_places_search_bar')),
          matching: find.byType(TextField),
        );
        await tester.enterText(destSearchInput, _clockTowerPlaceName);
        await tester.pump(const Duration(milliseconds: 350));
        await _pumpFrames(tester, 6);

        await tester.tap(
          find.byKey(const Key('dest_place_tile_$_clockTowerPlaceId')),
        );
        await _pumpFrames(tester, 6);
        expect(find.byType(PlaceDetailScreen), findsOneWidget);

        // Bấm Lưu khi chưa đăng nhập -> chuyển tới /login?redirect=%2Fplaces%2F65562a67-...
        await tester.tap(find.byKey(const Key('place_detail_save_to_trip')));
        await _pumpFrames(tester, 6);

        final loginUri = container
            .read(appRouterProvider)
            .routeInformationProvider
            .value
            .uri;
        expect(loginUri.path, '/login');
        expect(
          loginUri.queryParameters['redirect'],
          '/places/$_clockTowerPlaceId',
        );
        expect(find.byKey(const Key('login_redirect_notice')), findsOneWidget);

        // Đăng nhập -> tự động quay về đúng Tháp Đồng Hồ
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
        expect(postLoginUri.path, '/places/$_clockTowerPlaceId');
        expect(find.byType(PlaceDetailScreen), findsOneWidget);
        expect(find.text(_clockTowerPlaceName), findsOneWidget);

        // Lưu Tháp Đồng Hồ ngay sau khi quay về
        await tester.tap(find.byKey(const Key('place_detail_save_to_trip')));
        await _pumpFrames(tester, 6);
        await tester.tap(find.byKey(const Key('trip_picker_confirm_save')));
        await _pumpFrames(tester, 6);

        expect(backend.createTripCallCount, 1);
        expect(
          find.textContaining('Đã lưu "$_clockTowerPlaceName"'),
          findsOneWidget,
        );
      },
    );
  });
}
