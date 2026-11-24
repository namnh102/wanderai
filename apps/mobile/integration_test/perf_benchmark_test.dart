import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/features/home/presentation/home_screen.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_detail_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_list_screen.dart';

const _haLongDestId = '4eec2f30-b67d-4221-b754-8fcc7bb1160e';
const _clockTowerId = '65562a67-84ff-44a0-990d-31917a2a9bd0';

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
        position: const LatLng(20.95161, 107.08520),
        accuracyMeters: 15,
        timestamp: DateTime(2026, 11, 25, 1, 45),
      );
  @override
  Future<LatLng> currentPosition() async => const LatLng(20.95161, 107.08520);
  @override
  Future<bool> openAppSettings() async => true;
  @override
  Future<bool> openLocationSettings() async => true;
}

class _PerfBackendAdapter implements HttpClientAdapter {
  late final List<Map<String, dynamic>> _places = List.generate(40, (idx) {
    final isClock = idx == 22;
    return <String, dynamic>{
      'id': isClock
          ? _clockTowerId
          : '00000000-0000-4000-8000-${idx.toString().padLeft(12, '0')}',
      'name': isClock ? 'Tháp Đồng Hồ' : 'Địa điểm Hạ Long #${idx + 1}',
      'address': 'Hạ Long, Quảng Ninh',
      'latitude': 20.95 + idx * 0.001,
      'longitude': 107.07 + idx * 0.001,
      'rating': 4.6,
      'reviewCount': 10 + idx,
      'isVerified': true,
      'category': {'name': 'attraction'},
      'destination': {
        'id': _haLongDestId,
        'name': 'Hạ Long',
        'slug': 'ha-long',
      },
    };
  });

  late final List<Map<String, dynamic>> _trips = List.generate(35, (idx) {
    final id = idx == 0 ? 'trip-perf-001' : 'trip-perf-${idx + 1}';
    return <String, dynamic>{
      'id': id,
      'userId': 'user-perf-1',
      'destinationId': _haLongDestId,
      'destination': {
        'id': _haLongDestId,
        'name': 'Hạ Long',
        'slug': 'ha-long',
      },
      'title': idx == 0
          ? 'Hành trình Tháp Đồng Hồ Hạ Long'
          : 'Chuyến đi Hạ Long #${idx + 1}',
      'description': 'Benchmark itinerary dataset #$idx',
      'status': 'PLANNED',
      'totalBudget': 3000000 + idx * 100000,
      'currency': 'VND',
      'travelStyle': 'COMFORT',
      'interests': const ['culture', 'nature'],
      'itineraries': idx == 0
          ? List.generate(6, (dayIdx) {
              return {
                'id': 'itin-day-${dayIdx + 1}',
                'dayNumber': dayIdx + 1,
                'title': 'Ngày ${dayIdx + 1}: Khám phá Hạ Long',
                'items': List.generate(6, (itemIdx) {
                  final globalIdx = dayIdx * 6 + itemIdx + 1;
                  return {
                    'id': 'itin-item-$globalIdx',
                    'orderIndex': itemIdx + 1,
                    'activity': globalIdx == 1
                        ? 'Tham quan Tháp Đồng Hồ'
                        : 'Hoạt động khám phá #$globalIdx',
                    'placeId': globalIdx == 1 ? _clockTowerId : null,
                    'startTime': '${(8 + itemIdx).toString().padLeft(2, '0')}:00',
                    'estimatedCost': 50000 * (itemIdx + 1),
                    'notes': 'Điểm dừng chân #$globalIdx tại Hạ Long',
                  };
                }),
              };
            })
          : <Map<String, dynamic>>[],
    };
  });

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final method = options.method.toUpperCase();
    final path = options.path;

    if (method == 'GET' && path == '/destinations') {
      return _json(200, {
        'success': true,
        'data': {
          'items': [
            {
              'id': _haLongDestId,
              'name': 'Hạ Long',
              'slug': 'ha-long',
              'province': 'Quảng Ninh',
              'region': 'north',
              'latitude': 20.9516,
              'longitude': 107.0852,
              'description': 'Vịnh Hạ Long & Tháp Đồng Hồ.',
              'rating': 4.8,
              'reviewCount': 42,
              'isPopular': true,
              '_count': {'places': 40},
            },
          ],
        },
      });
    }

    if (method == 'GET' && path == '/places/trending') {
      return _json(200, {
        'success': true,
        'data': {'items': _places.take(6).toList()},
      });
    }

    if (method == 'GET' && path == '/places') {
      final page =
          int.tryParse(options.queryParameters['page']?.toString() ?? '') ?? 1;
      final limit =
          int.tryParse(options.queryParameters['limit']?.toString() ?? '') ??
              20;
      final start = (page - 1) * limit;
      final slice = start >= _places.length
          ? const <Map<String, dynamic>>[]
          : _places.skip(start).take(limit).toList();
      return _json(200, {
        'success': true,
        'data': {'items': slice, 'total': _places.length},
      });
    }

    if (method == 'GET' && path == '/users/me') {
      return _json(200, {
        'success': true,
        'data': {
          'id': 'user-perf-1',
          'email': 'perf@gomate.vn',
          'profile': {'displayName': 'Perf Runner'},
          'preferences': {'interests': ['culture']},
        },
      });
    }

    if (method == 'GET' && path == '/trips') {
      return _json(200, {'success': true, 'data': _trips});
    }

    final tripMatch = RegExp(r'^/trips/([^/]+)$').firstMatch(path);
    if (method == 'GET' && tripMatch != null) {
      final trip = _trips.firstWhere(
        (t) => t['id'] == tripMatch.group(1),
        orElse: () => _trips.first,
      );
      return _json(200, {'success': true, 'data': trip});
    }

    return _json(404, {'message': 'Not found'});
  }

  ResponseBody _json(int code, Map<String, dynamic> payload) {
    return ResponseBody.fromString(
      jsonEncode(payload),
      code,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Profile perf benchmark: DestinationPlacesSheet, TripList, TripDetail',
      (tester) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', 'perf-jwt-access');
    await prefs.setString('refresh_token', 'perf-jwt-refresh');

    final backend = _PerfBackendAdapter();
    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(_PassiveLocationService()),
        apiClientProvider.overrideWith((ref) {
          final epoch = ref.read(sessionEpochControllerProvider);
          return createApiClient(
            baseUrlOverride: 'https://perf.gomate.local',
            sessionEpoch: epoch,
          )..httpClientAdapter = backend;
        }),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp.router(
          debugShowCheckedModeBanner: false,
          theme: AppTheme.lightTheme,
          routerConfig: container.read(appRouterProvider),
        ),
      ),
    );
    await tester.pumpAndSettle(const Duration(seconds: 2));
    expect(find.byType(HomeScreen), findsOneWidget);

    // 1. DestinationPlacesSheet open latency + scroll trace
    final destOpenSw = Stopwatch()..start();
    final haLongCard = find.byKey(const Key('home_dest_ha-long'));
    await tester.ensureVisible(haLongCard);
    await tester.tap(haLongCard);
    await tester.pumpAndSettle(const Duration(seconds: 2));
    destOpenSw.stop();
    final destSheetOpenMs = destOpenSw.elapsedMilliseconds;

    final destListFinder = find.byType(ListView).last;
    await binding.traceAction(() async {
      await tester.fling(destListFinder, const Offset(0, -600), 1400);
      await tester.pumpAndSettle(const Duration(seconds: 2));
      await tester.fling(destListFinder, const Offset(0, 450), 1200);
      await tester.pumpAndSettle(const Duration(seconds: 2));
    }, reportKey: 'dest_sheet_scroll');

    Navigator.of(
      tester.element(find.byKey(const Key('destination_places_search_bar'))),
    ).pop();
    await tester.pumpAndSettle();

    // 2. TripListScreen open latency + scroll trace
    final tripListOpenSw = Stopwatch()..start();
    container.read(appRouterProvider).go('/trips');
    await tester.pumpAndSettle(const Duration(seconds: 2));
    tripListOpenSw.stop();
    final tripListOpenMs = tripListOpenSw.elapsedMilliseconds;
    expect(find.byType(TripListScreen), findsOneWidget);

    final tripListScrollFinder = find.byType(ListView).first;
    await binding.traceAction(() async {
      await tester.fling(tripListScrollFinder, const Offset(0, -700), 1600);
      await tester.pumpAndSettle(const Duration(seconds: 2));
      await tester.fling(tripListScrollFinder, const Offset(0, 700), 1600);
      await tester.pumpAndSettle(const Duration(seconds: 2));
    }, reportKey: 'trip_list_scroll');

    // 3. TripDetailScreen (36 items across 6 days) open latency + scroll trace
    final tripDetailOpenSw = Stopwatch()..start();
    await tester.tap(find.byKey(const Key('trip_card_trip-perf-001')));
    await tester.pumpAndSettle(const Duration(seconds: 2));
    tripDetailOpenSw.stop();
    final tripDetailOpenMs = tripDetailOpenSw.elapsedMilliseconds;
    expect(find.byType(TripDetailScreen), findsOneWidget);

    final tripDetailScrollFinder = find.byType(Scrollable).first;
    await binding.traceAction(() async {
      await tester.fling(tripDetailScrollFinder, const Offset(0, -800), 1600);
      await tester.pumpAndSettle(const Duration(seconds: 2));
      await tester.fling(tripDetailScrollFinder, const Offset(0, 800), 1600);
      await tester.pumpAndSettle(const Duration(seconds: 2));
    }, reportKey: 'trip_detail_scroll');

    binding.reportData ??= <String, dynamic>{};
    binding.reportData!['custom_metrics'] = <String, dynamic>{
      'dest_sheet_open_ms': destSheetOpenMs,
      'trip_list_open_ms': tripListOpenMs,
      'trip_detail_open_ms': tripDetailOpenMs,
    };
  });
}
