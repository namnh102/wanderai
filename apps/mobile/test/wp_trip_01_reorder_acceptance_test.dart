import 'dart:async';
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
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/trips/data/trip_models.dart';
import 'package:wanderai_mobile/features/trips/data/trip_repository.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_detail_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_list_screen.dart';
import 'package:wanderai_mobile/features/trips/providers/trip_provider.dart';

const _haLongDestinationId = '4eec2f30-b67d-4221-b754-8fcc7bb1160e';
const _placeAId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
const _placeAName = 'Tháp Đồng Hồ';
const _placeBId = '8f2b5a69-1293-4efe-8fc5-3a74193edd0f';
const _placeBName = 'Bảo tàng Quảng Ninh';
const _validAccessToken = 'jwt-access-wp-trip-01';
const _validRefreshToken = 'jwt-refresh-wp-trip-01';

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
        timestamp: DateTime(2026, 11, 25, 19, 0),
      );

  @override
  Future<LatLng> currentPosition() async => const LatLng(20.95161, 107.08520);

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;
}

class _ReorderStatefulBackendAdapter implements HttpClientAdapter {
  final List<(String method, String path)> recordedCalls = [];
  int failReorderRemaining;

  final Map<String, dynamic> _trip = {
    'id': 'trip-wp-01-halong',
    'userId': 'user-wp-01',
    'destinationId': _haLongDestinationId,
    'destination': {
      'id': _haLongDestinationId,
      'name': 'Hạ Long',
      'slug': 'ha-long',
    },
    'title': 'Chuyến thử Hạ Long WP-TRIP-01',
    'description': 'Nghiệm thu kéo đổi thứ tự A -> B thành B -> A',
    'status': 'PLANNED',
    'currency': 'VND',
    'interests': <String>['culture'],
    'itineraries': <Map<String, dynamic>>[
      {
        'id': 'itin-day-1',
        'tripId': 'trip-wp-01-halong',
        'dayNumber': 1,
        'title': 'Ngày 1',
        'items': <Map<String, dynamic>>[
          {
            'id': 'item-a-clock-tower',
            'itineraryId': 'itin-day-1',
            'orderIndex': 1,
            'activity': 'Tham quan $_placeAName',
            'placeId': _placeAId,
            'place': {
              'id': _placeAId,
              'name': _placeAName,
              'address': 'Hạ Long, Quảng Ninh',
            },
          },
          {
            'id': 'item-b-museum',
            'itineraryId': 'itin-day-1',
            'orderIndex': 2,
            'activity': 'Tham quan $_placeBName',
            'placeId': _placeBId,
            'place': {
              'id': _placeBId,
              'name': _placeBName,
              'address': 'Hạ Long, Quảng Ninh',
            },
          },
        ],
      },
    ],
  };

  _ReorderStatefulBackendAdapter({this.failReorderRemaining = 0});

  List<String> get apiOrderedPlaceIds {
    final days = (_trip['itineraries'] as List).cast<Map<String, dynamic>>();
    final items =
        List<Map<String, dynamic>>.from(days.first['items'] as List<dynamic>)
          ..sort(
            (a, b) =>
                (a['orderIndex'] as int).compareTo(b['orderIndex'] as int),
          );
    return items.map((e) => e['placeId'] as String).toList();
  }

  Map<String, dynamic> _serializedTrip() {
    final copy = jsonDecode(jsonEncode(_trip)) as Map<String, dynamic>;
    final days = (copy['itineraries'] as List).cast<Map<String, dynamic>>();
    for (final d in days) {
      final items = (d['items'] as List).cast<Map<String, dynamic>>();
      items.sort(
        (a, b) => (a['orderIndex'] as int).compareTo(b['orderIndex'] as int),
      );
    }
    return copy;
  }

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final method = options.method.toUpperCase();
    final path = options.path;
    recordedCalls.add((method, path));

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
              'rating': 4.8,
              'reviewCount': 42,
              'isPopular': true,
              '_count': {'places': 197},
            },
          ],
        },
      });
    }

    if (method == 'GET' && path == '/places/trending') {
      return _json(200, {'success': true, 'data': <Map<String, dynamic>>[]});
    }

    if (method == 'GET' && path == '/users/me') {
      return _json(200, {
        'success': true,
        'data': {
          'id': 'user-wp-01',
          'email': 'tester@gomate.vn',
          'profile': {'displayName': 'WP-TRIP-01 Tester'},
          'preferences': {
            'interests': ['culture']
          },
        },
      });
    }

    if (method == 'GET' && path == '/trips') {
      return _json(200, {
        'success': true,
        'data': [_serializedTrip()],
      });
    }

    if (method == 'GET' && path == '/trips/trip-wp-01-halong') {
      return _json(200, {
        'success': true,
        'data': _serializedTrip(),
      });
    }

    if (method == 'PUT' &&
        path == '/trips/trip-wp-01-halong/itinerary/reorder') {
      if (failReorderRemaining > 0) {
        failReorderRemaining--;
        return _json(503, {
          'message': 'Máy chủ tạm thời gián đoạn khi lưu thứ tự lịch trình',
        });
      }
      final body = Map<String, dynamic>.from(options.data as Map);
      final updates = (body['items'] as List).cast<Map<String, dynamic>>();
      final days = (_trip['itineraries'] as List).cast<Map<String, dynamic>>();
      final items = (days.first['items'] as List).cast<Map<String, dynamic>>();
      for (final upd in updates) {
        final match = items.firstWhere((i) => i['id'] == upd['itemId']);
        match['orderIndex'] = upd['orderIndex'] as int;
      }
      items.sort(
        (a, b) => (a['orderIndex'] as int).compareTo(b['orderIndex'] as int),
      );
      return _json(200, {
        'success': true,
        'data': _serializedTrip(),
      });
    }

    return _json(404, {'message': 'Unhandled $method $path'});
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

class _DeferredReorderRepo extends TripRepository {
  final Completer<TripModel> reorderCompleter = Completer<TripModel>();
  _DeferredReorderRepo() : super(Dio());

  @override
  Future<TripModel> reorderItineraryItems(
    String tripId,
    ReorderItineraryRequest request,
  ) =>
      reorderCompleter.future;
}

ProviderContainer _createContainer(_ReorderStatefulBackendAdapter backend) {
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

Future<void> _pumpFrames(WidgetTester tester, [int count = 5]) async {
  for (var i = 0; i < count; i++) {
    await tester.pump(const Duration(milliseconds: 60));
  }
}

void main() {
  group(
      'WP-TRIP-01 Mobile Acceptance — Drag A -> B to B -> A, Save, Close, Reopen & Reconcile API',
      () {
    testWidgets(
      'Acceptance Case: kéo đổi A (Tháp Đồng Hồ) -> B (Bảo tàng Quảng Ninh) thành B -> A, lưu, đóng hẳn app, mở lại đúng chuyến và đối chiếu UI == API == [B, A]',
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
        final backend = _ReorderStatefulBackendAdapter();

        // ── SESSION 1: Mở chuyến đi có A -> B ──
        final container1 = _createContainer(backend);
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

        await tester.tap(find.text('Chuyến đi'));
        await _pumpFrames(tester, 6);
        expect(find.byType(TripListScreen), findsOneWidget);

        await tester.tap(find.byKey(const Key('trip_card_trip-wp-01-halong')));
        await _pumpFrames(tester, 6);
        expect(find.byType(TripDetailScreen), findsOneWidget);

        // Cuộn tới Lịch trình chi tiết để thấy cả A và B
        final reorderToggle =
            find.byKey(const Key('trip_itinerary_reorder_toggle'));
        await tester.scrollUntilVisible(
          reorderToggle,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await _pumpFrames(tester, 3);

        final beforePosA = tester
            .getCenter(find.byKey(const Key('trip_item_place_$_placeAId')));
        final beforePosB = tester
            .getCenter(find.byKey(const Key('trip_item_place_$_placeBId')));
        expect(
          beforePosA.dy < beforePosB.dy,
          isTrue,
          reason:
              'Trước khi kéo đổi thứ tự, A (Tháp Đồng Hồ) phải đứng trên B (Bảo tàng Quảng Ninh)',
        );
        expect(backend.apiOrderedPlaceIds, [_placeAId, _placeBId]);

        // 1. Bật chế độ Đổi thứ tự
        await tester.tap(reorderToggle);
        await _pumpFrames(tester, 4);
        expect(
          find.byKey(const Key('trip_itinerary_reorder_toolbar')),
          findsOneWidget,
        );

        final handleB =
            find.byKey(const Key('trip_reorder_handle_item-b-museum'));
        await Scrollable.ensureVisible(
          tester.element(handleB),
          alignment: 0.5,
        );
        await _pumpFrames(tester, 2);

        // 2. Kéo B lên trên A (A -> B thành B -> A) bằng cử chỉ kéo đa khung hình thực tế
        await tester.timedDrag(
          handleB,
          const Offset(0, -120),
          const Duration(milliseconds: 300),
        );
        await tester.pumpAndSettle();

        final draftPosB = tester.getCenter(
          find.byKey(const Key('trip_reorder_place_$_placeBId')),
        );
        final draftPosA = tester.getCenter(
          find.byKey(const Key('trip_reorder_place_$_placeAId')),
        );
        expect(
          draftPosB.dy < draftPosA.dy,
          isTrue,
          reason: 'Sau thao tác kéo, B phải nằm trên A trong bản nháp',
        );
        // Chưa bấm Lưu thì API vẫn giữ A -> B
        expect(backend.apiOrderedPlaceIds, [_placeAId, _placeBId]);

        // 3. Nhấn Lưu thứ tự
        final saveBtn = find.byKey(const Key('trip_itinerary_reorder_save'));
        await tester.ensureVisible(saveBtn);
        await tester.tap(saveBtn);
        await _pumpFrames(tester, 6);

        expect(
          find.byKey(const Key('trip_itinerary_reorder_saved_snackbar')),
          findsOneWidget,
        );
        expect(
          backend.recordedCalls.where(
            (c) =>
                c.$1 == 'PUT' &&
                c.$2 == '/trips/trip-wp-01-halong/itinerary/reorder',
          ),
          hasLength(1),
        );
        expect(backend.apiOrderedPlaceIds, [_placeBId, _placeAId]);

        // 4. Đóng hẳn app (unmount toàn bộ widget tree + dispose ProviderContainer)
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump();
        container1.dispose();

        // 5. Mở lại app từ đầu -> vào Chuyến đi -> mở đúng chuyến -> đối chiếu UI & API
        final container2 = _createContainer(backend);
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

        await tester.tap(find.byKey(const Key('trip_card_trip-wp-01-halong')));
        await _pumpFrames(tester, 6);
        expect(find.byType(TripDetailScreen), findsOneWidget);

        await tester.scrollUntilVisible(
          find.byKey(const Key('trip_item_place_$_placeAId')),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await _pumpFrames(tester, 3);

        final reopenedPosB = tester.getCenter(
          find.byKey(const Key('trip_item_place_$_placeBId')),
        );
        final reopenedPosA = tester.getCenter(
          find.byKey(const Key('trip_item_place_$_placeAId')),
        );
        expect(
          reopenedPosB.dy < reopenedPosA.dy,
          isTrue,
          reason:
              'Sau khi đóng hẳn app và mở lại chuyến, B phải hiển thị trước A trên giao diện Android',
        );

        final reopenedItems =
            container2.read(tripDetailProvider).trip!.itineraries.single.items;
        final uiOrderedPlaceIds = reopenedItems.map((i) => i.placeId!).toList();
        final uiOrderIndices = reopenedItems.map((i) => i.orderIndex).toList();

        expect(uiOrderIndices, [1, 2]);
        expect(uiOrderedPlaceIds, [_placeBId, _placeAId]);
        expect(backend.apiOrderedPlaceIds, [_placeBId, _placeAId]);
        expect(uiOrderedPlaceIds, equals(backend.apiOrderedPlaceIds));
      },
    );

    testWidgets(
      'Cancel & Retry Resilience: Hủy khôi phục A -> B không gọi API; lỗi 503 giữ nguyên thứ tự kéo B -> A để bấm Lưu lại thành công',
      (tester) async {
        tester.view.physicalSize = const Size(360, 800);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        SharedPreferences.setMockInitialValues({
          'access_token': _validAccessToken,
          'refresh_token': _validRefreshToken,
        });
        final backend = _ReorderStatefulBackendAdapter(failReorderRemaining: 1);
        final container = _createContainer(backend);
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

        container.read(appRouterProvider).push('/trips/trip-wp-01-halong');
        await _pumpFrames(tester, 6);

        final reorderToggle =
            find.byKey(const Key('trip_itinerary_reorder_toggle'));
        await tester.scrollUntilVisible(
          reorderToggle,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await _pumpFrames(tester, 2);

        // Kéo B lên trên A rồi nhấn Hủy
        await tester.tap(reorderToggle);
        await _pumpFrames(tester, 3);
        final handleB =
            find.byKey(const Key('trip_reorder_handle_item-b-museum'));
        await tester.ensureVisible(handleB);
        await tester.timedDrag(
          handleB,
          const Offset(0, -120),
          const Duration(milliseconds: 300),
        );
        await tester.pumpAndSettle();

        await tester
            .tap(find.byKey(const Key('trip_itinerary_reorder_cancel')));
        await _pumpFrames(tester, 3);
        expect(
          backend.recordedCalls.where((c) => c.$1 == 'PUT'),
          isEmpty,
        );

        // Mở lại Đổi thứ tự -> kéo B lên trên A -> lần Lưu đầu lỗi 503 -> giữ nguyên B -> A -> Lưu lại thành công
        await tester.tap(reorderToggle);
        await _pumpFrames(tester, 3);
        await tester.ensureVisible(handleB);
        await tester.timedDrag(
          handleB,
          const Offset(0, -120),
          const Duration(milliseconds: 300),
        );
        await tester.pumpAndSettle();

        final saveBtn = find.byKey(const Key('trip_itinerary_reorder_save'));
        await tester.ensureVisible(saveBtn);
        await tester.tap(saveBtn);
        await _pumpFrames(tester, 4);

        expect(
          find.byKey(const Key('trip_itinerary_error_snackbar')),
          findsOneWidget,
        );
        // Vẫn ở chế độ kéo đổi thứ tự và giữ nguyên B -> A
        expect(
          find.byKey(const Key('trip_itinerary_reorder_toolbar')),
          findsOneWidget,
        );

        ScaffoldMessenger.of(tester.element(find.byType(TripDetailScreen)))
            .clearSnackBars();
        await tester.pump();

        // Lần Lưu thứ 2 thành công
        await tester.tap(saveBtn);
        await _pumpFrames(tester, 5);
        expect(backend.apiOrderedPlaceIds, [_placeBId, _placeAId]);
      },
    );

    test(
      'Disposing TripDetailNotifier mid-flight during reorderItineraryItems throws zero StateErrors',
      () async {
        final repo = _DeferredReorderRepo();
        final notifier = TripDetailNotifier(repo);
        final future = notifier.reorderItineraryItems(
          'trip-1',
          const ReorderItineraryRequest(
            items: [ReorderItineraryItemEntry(itemId: 'i-1', orderIndex: 1)],
          ),
        );
        notifier.dispose();
        repo.reorderCompleter.complete(
          const TripModel(id: 'trip-1', userId: 'u-1', title: 'Disposed'),
        );
        expect(await future, isFalse);
      },
    );
  });
}
