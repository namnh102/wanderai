// Live E2E acceptance test against a RUNNING stack (PostgreSQL + NestJS on :3000).
//
// Opt-in only: skipped unless `LIVE_HALONG_E2E=1` so offline `flutter test` stays deterministic.
// Acceptance POI: `65562a67-84ff-44a0-990d-31917a2a9bd0` (Tháp Đồng Hồ | Hạ Long).
//   $env:LIVE_HALONG_E2E='1'; flutter test test/live_halong_trip_save_e2e_test.dart --reporter expanded
@TestOn('vm')
library;

import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:latlong2/latlong.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/home/providers/home_provider.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/map/providers/map_provider.dart';
import 'package:wanderai_mobile/features/places/providers/place_detail_provider.dart';
import 'package:wanderai_mobile/features/trips/data/trip_models.dart';
import 'package:wanderai_mobile/features/trips/providers/trip_provider.dart';

const _defaultHaLongPlaceId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
const _defaultHaLongSearchTerm = 'Tháp Đồng Hồ';
const _haLongSlug = 'ha-long';

class _NoopLocationService implements LocationService {
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
        timestamp: DateTime.now(),
      );

  @override
  Future<LatLng> currentPosition() async => const LatLng(20.95125, 107.08190);

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;
}

void _logStep(String step) {
  final ts = DateTime.now().toIso8601String();
  stdout.writeln('[$ts] [HALONG-ACCEPTANCE-E2E] $step');
}

ProviderContainer _buildLiveContainer(String baseUrl) {
  return ProviderContainer(
    overrides: [
      locationServiceProvider.overrideWithValue(_NoopLocationService()),
      apiClientProvider.overrideWith((ref) {
        final epoch = ref.read(sessionEpochControllerProvider);
        return createApiClient(
          baseUrlOverride: baseUrl,
          sessionEpoch: epoch,
          onSessionExpired: () {
            ref.read(authSessionExpiredSignalProvider.notifier).state++;
          },
        );
      }),
    ],
  );
}

Future<void> _waitForAuthSettled(ProviderContainer container) async {
  for (var i = 0; i < 40; i++) {
    if (container.read(authProvider).status != AuthStatus.unknown) {
      return;
    }
    await Future<void>.delayed(const Duration(milliseconds: 25));
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  HttpOverrides.global = null; // Real TCP sockets against localhost:3000

  final live = Platform.environment['LIVE_HALONG_E2E'] == '1';
  final baseUrl =
      Platform.environment['LIVE_API_BASE_URL'] ?? 'http://localhost:3000';
  final targetPlaceId =
      (Platform.environment['TARGET_PLACE_ID'] ?? _defaultHaLongPlaceId).trim();
  final searchTerm =
      (Platform.environment['TARGET_PLACE_SEARCH'] ?? _defaultHaLongSearchTerm)
          .trim();

  group(
    'Live Acceptance — 65562a67-84ff-44a0-990d-31917a2a9bd0 | Tháp Đồng Hồ | Hạ Long',
    () {
      late String testEmail;
      const testPassword = 'HaLongPass#2026';
      late String persistedAccessToken;
      late String persistedRefreshToken;

      test(
        'Case 1 (Live): Khám phá Hạ Long -> tìm Tháp Đồng Hồ -> mở chi tiết -> lưu vào chuyến -> đóng hẳn app -> mở lại -> mở chuyến',
        () async {
          final stamp = DateTime.now().millisecondsSinceEpoch;
          testEmail = 'thap_dong_ho_$stamp@gomate.vn';

          SharedPreferences.setMockInitialValues({});

          // ── SESSION 1: Khởi động app & đăng ký tài khoản kiểm thử ──
          final container1 = _buildLiveContainer(baseUrl);
          container1.read(routerNotifierProvider);
          await _waitForAuthSettled(container1);
          expect(
            container1.read(authProvider).status,
            AuthStatus.unauthenticated,
          );

          _logStep('Session #1: Registering user $testEmail against $baseUrl');
          final registered = await container1
              .read(authProvider.notifier)
              .register('Tháp Đồng Hồ Tester', testEmail, testPassword);
          expect(
            registered,
            isTrue,
            reason: container1.read(authProvider).errorMessage,
          );

          final prefs1 = await SharedPreferences.getInstance();
          persistedAccessToken = prefs1.getString('access_token')!;
          persistedRefreshToken = prefs1.getString('refresh_token')!;

          // 1. Khám phá Hạ Long
          final homeSub = container1.listen(homeProvider, (_, __) {});
          await container1.read(homeProvider.notifier).load();
          final haLongDest = container1
              .read(homeProvider)
              .destinations
              .firstWhere((d) => d.slug == _haLongSlug);
          _logStep(
            'Step 1 (Khám phá Hạ Long): destination="${haLongDest.name}" destination_id=${haLongDest.id} total_verified=${haLongDest.placeCount}',
          );

          // Kiểm tra trang 1 mặc định (limit=20, không search) và tìm kiếm "Tháp Đồng Hồ" trong DestinationPlacesSheet
          final page1Default =
              await container1.read(placeRepositoryProvider).getPlaces(
                    destinationId: haLongDest.id,
                    verifiedOnly: true,
                    limit: 20,
                  );
          final inDefaultTop20 = page1Default.any((p) => p.id == targetPlaceId);
          _logStep(
            'Step 1b (Kiểm tra trang 1 mặc định limit=20): count=${page1Default.length}, contains_target_without_search=$inDefaultTop20',
          );

          final searchedInSheet =
              await container1.read(placeRepositoryProvider).getPlaces(
                    destinationId: haLongDest.id,
                    search: searchTerm,
                    verifiedOnly: true,
                    limit: 20,
                  );
          final matchedPlace = searchedInSheet.firstWhere(
            (p) => p.id == targetPlaceId,
          );
          _logStep(
            'Step 2 (Tìm "$searchTerm" trong Khám phá Hạ Long): FOUND place_id=${matchedPlace.id} | name="${matchedPlace.name}" | destination="${matchedPlace.destinationName}"',
          );

          // 2. Mở chi tiết Tháp Đồng Hồ (GET /places/:id)
          final placeDetail = await container1.read(
            placeDetailProvider(targetPlaceId).future,
          );
          expect(placeDetail.id, targetPlaceId);
          expect(placeDetail.isVerified, isTrue);
          _logStep(
            'Step 3 (Mở chi tiết POI): route=/places/${placeDetail.id} | name="${placeDetail.name}" | isVerified=${placeDetail.isVerified}',
          );

          // 3. Tạo/chọn chuyến & Lưu Tháp Đồng Hồ vào chuyến
          final createdTrip =
              await container1.read(tripListProvider.notifier).createTrip(
                    CreateTripRequest(
                      title: 'Nghiệm thu Tháp Đồng Hồ Hạ Long $stamp',
                      destinationId: placeDetail.destinationId ?? haLongDest.id,
                      description: 'Nghiệm thu phiên C Tháp Đồng Hồ',
                    ),
                  );
          expect(createdTrip, isNotNull);

          final savedItem =
              await container1.read(tripRepositoryProvider).addItineraryItem(
                    createdTrip!.id,
                    AddItineraryItemRequest(
                      dayNumber: 1,
                      activity: 'Tham quan ${placeDetail.name}',
                      placeId: placeDetail.id,
                    ),
                  );
          expect(savedItem.placeId, targetPlaceId);
          _logStep(
            'Step 4 [BEFORE APP CLOSE]: SAVED place_id=${savedItem.placeId} ("${placeDetail.name}") -> trip_id=${createdTrip.id} ("${createdTrip.title}") item_id=${savedItem.id} day=1',
          );

          // 4. Đóng hẳn app (dispose toàn bộ Riverpod state trong RAM)
          homeSub.close();
          container1.dispose();
          _logStep(
            'Step 5 [APP CLOSED]: Session #1 ProviderContainer disposed completely (RAM state wiped)',
          );

          // 5. Mở lại app từ đầu (chỉ đọc JWT từ SharedPreferences + dữ liệu từ PostgreSQL)
          SharedPreferences.setMockInitialValues({
            'access_token': persistedAccessToken,
            'refresh_token': persistedRefreshToken,
          });
          final container2 = _buildLiveContainer(baseUrl);
          addTearDown(container2.dispose);
          container2.read(routerNotifierProvider);
          await _waitForAuthSettled(container2);
          expect(
            container2.read(authProvider).status,
            AuthStatus.authenticated,
          );
          _logStep(
            'Step 6 [APP REOPENED]: Session #2 cold-started; session restored from SharedPreferences',
          );

          // 6. Mở danh sách chuyến -> mở chuyến vừa lưu -> xác minh place_id & trip_id khớp tuyệt đối
          await container2.read(tripListProvider.notifier).loadTrips();
          final reopenedSummary = container2
              .read(tripListProvider)
              .trips
              .firstWhere((t) => t.id == createdTrip.id);

          await container2
              .read(tripDetailProvider.notifier)
              .loadTrip(reopenedSummary.id);
          final reopenedTrip = container2.read(tripDetailProvider).trip!;
          final reopenedItem = reopenedTrip.itineraries
              .firstWhere((d) => d.dayNumber == 1)
              .items
              .firstWhere((i) => i.placeId == targetPlaceId);

          expect(reopenedTrip.id, createdTrip.id);
          expect(reopenedItem.id, savedItem.id);
          expect(reopenedItem.placeId, targetPlaceId);
          expect(reopenedItem.placeName, placeDetail.name);

          _logStep(
            'Step 7 [AFTER APP REOPEN]: VERIFIED trip_id=${reopenedTrip.id} ("${reopenedTrip.title}") CONTAINS place_id=${reopenedItem.placeId} ("${reopenedItem.placeName}") item_id=${reopenedItem.id} activity="${reopenedItem.activity}"',
          );
        },
      );

      test(
        'Case 2 (Live): Chưa đăng nhập bấm lưu tại Tháp Đồng Hồ -> đăng nhập -> quay về đúng Tháp Đồng Hồ -> lưu vào chuyến',
        () async {
          SharedPreferences.setMockInitialValues({});
          final container = _buildLiveContainer(baseUrl);
          addTearDown(container.dispose);
          final routerNotifier = container.read(routerNotifierProvider);
          await _waitForAuthSettled(container);
          expect(
            container.read(authProvider).status,
            AuthStatus.unauthenticated,
          );

          // 1. Khách chưa đăng nhập mở chi tiết Tháp Đồng Hồ
          container.read(guestBrowseModeProvider.notifier).state = true;
          final guestPoi = await container.read(
            placeDetailProvider(targetPlaceId).future,
          );
          expect(guestPoi.id, targetPlaceId);
          _logStep(
            'Case 2 Step 1 (Guest): Opened /places/${guestPoi.id} ("${guestPoi.name}") while unauthenticated',
          );

          // 2. Bấm Lưu khi chưa đăng nhập -> chuyển tới /login?redirect=%2Fplaces%2F65562a67-...
          final intendedPoiRoute = '/places/${guestPoi.id}';
          container.read(postLoginRedirectProvider.notifier).state =
              intendedPoiRoute;
          final loginUrl =
              '/login?redirect=${Uri.encodeComponent(intendedPoiRoute)}';
          final parsedLoginUri = Uri.parse(loginUrl);
          _logStep(
            'Case 2 Step 2 (Unauth Save Tap): Redirected to $loginUrl',
          );

          // 3. Đăng nhập thật qua POST /auth/login
          final loggedIn = await container
              .read(authProvider.notifier)
              .login(testEmail, testPassword);
          expect(loggedIn, isTrue);

          // 4. Xác minh RouterNotifier trả người dùng về đúng /places/65562a67-84ff-44a0-990d-31917a2a9bd0
          final resolvedRoute = routerNotifier.resolvePostAuthDestination(
            queryRedirect: parsedLoginUri.queryParameters['redirect'],
          );
          expect(resolvedRoute, intendedPoiRoute);
          _logStep(
            'Case 2 Step 3 (Post-Login Redirect): Returned to exact route $resolvedRoute ("${guestPoi.name}")',
          );

          // 5. Lưu vào chuyến ngay sau khi quay về Tháp Đồng Hồ
          await container.read(tripListProvider.notifier).loadTrips();
          final existingTrip = container.read(tripListProvider).trips.first;
          final postLoginItem =
              await container.read(tripRepositoryProvider).addItineraryItem(
                    existingTrip.id,
                    AddItineraryItemRequest(
                      dayNumber: 2,
                      activity: 'Tham quan ${guestPoi.name} (sau đăng nhập)',
                      placeId: guestPoi.id,
                    ),
                  );
          expect(postLoginItem.placeId, targetPlaceId);
          _logStep(
            'Case 2 Step 4 (Saved Post-Login): Saved place_id=${postLoginItem.placeId} -> trip_id=${existingTrip.id} item_id=${postLoginItem.id} day=2',
          );
        },
      );
    },
    skip:
        live ? false : 'set LIVE_HALONG_E2E=1 with PostgreSQL + NestJS running',
  );
}
