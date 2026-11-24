// Live E2E acceptance test against a RUNNING stack (PostgreSQL + NestJS on :3000).
//
// Opt-in only: skipped unless `LIVE_HALONG_E2E=1` so offline `flutter test` stays deterministic.
// Default POI: `0118b23e-ed95-4fc4-b26a-74b761e3eb6f` (Cảng tàu khách quốc tế Hạ Long).
// Override POI (e.g. when phiên C supplies `place_id`):
//   $env:LIVE_HALONG_E2E='1'; $env:TARGET_PLACE_ID='<place_uuid>'; flutter test test/live_halong_trip_save_e2e_test.dart
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

const _defaultHaLongPlaceId = '0118b23e-ed95-4fc4-b26a-74b761e3eb6f';
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
        position: const LatLng(20.95048, 107.05044),
        accuracyMeters: 15,
        timestamp: DateTime.now(),
      );

  @override
  Future<LatLng> currentPosition() async => const LatLng(20.95048, 107.05044);

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;
}

void _logStep(String step) {
  final ts = DateTime.now().toIso8601String();
  stdout.writeln('[$ts] [HALONG-LIVE-E2E] $step');
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
  HttpOverrides.global = null; // Use real OS sockets against localhost:3000

  final live = Platform.environment['LIVE_HALONG_E2E'] == '1';
  final baseUrl =
      Platform.environment['LIVE_API_BASE_URL'] ?? 'http://localhost:3000';
  final targetPlaceId =
      (Platform.environment['TARGET_PLACE_ID'] ?? _defaultHaLongPlaceId).trim();

  group(
    'Live Hạ Long POI -> Trip Save & Reopen Persistence',
    () {
      late String testEmail;
      const testPassword = 'HaLongPass#2026';
      late String persistedAccessToken;
      late String persistedRefreshToken;

      test(
        'Case 1 (Live): Khám phá Hạ Long -> mở chi tiết POI -> chọn chuyến -> lưu -> đóng và mở lại app -> mở chuyến vừa chọn',
        () async {
          final stamp = DateTime.now().millisecondsSinceEpoch;
          testEmail = 'halong_e2e_$stamp@gomate.vn';

          SharedPreferences.setMockInitialValues({});

          // ── SESSION 1: Launch app, register & sign in ──
          final container1 = _buildLiveContainer(baseUrl);
          container1.read(routerNotifierProvider);
          await _waitForAuthSettled(container1);
          expect(
              container1.read(authProvider).status, AuthStatus.unauthenticated);

          _logStep('Session #1: Registering test user $testEmail on $baseUrl');
          final registered = await container1
              .read(authProvider.notifier)
              .register('Ha Long Tester', testEmail, testPassword);
          expect(registered, isTrue,
              reason: container1.read(authProvider).errorMessage);
          expect(
              container1.read(authProvider).status, AuthStatus.authenticated);

          final prefs1 = await SharedPreferences.getInstance();
          persistedAccessToken = prefs1.getString('access_token')!;
          persistedRefreshToken = prefs1.getString('refresh_token')!;
          _logStep(
              'Session #1: Authenticated; tokens stored in SharedPreferences');

          // 1. Khám phá Hạ Long (HomeNotifier -> GET /destinations + DestinationPlacesSheet -> GET /places)
          // Giữ autoDispose homeProvider sống như khi HomeScreen đang mount trên màn hình.
          final homeSub = container1.listen(homeProvider, (_, __) {});
          await container1.read(homeProvider.notifier).load();
          final homeState = container1.read(homeProvider);
          final haLongDest = homeState.destinations.firstWhere(
            (d) => d.slug == _haLongSlug,
          );
          _logStep(
            'Step 1 (Khám phá Hạ Long): Loaded destination "${haLongDest.name}" (id=${haLongDest.id}, verifiedCount=${haLongDest.placeCount})',
          );

          final haLongPlaces =
              await container1.read(placeRepositoryProvider).getPlaces(
                    destinationId: haLongDest.id,
                    verifiedOnly: true,
                    limit: 50,
                  );
          expect(haLongPlaces, isNotEmpty);
          _logStep(
            'Step 1b (DestinationPlacesSheet): Loaded ${haLongPlaces.length} verified Hạ Long POIs',
          );

          // 2. Mở chi tiết POI (GET /places/:id)
          final placeDetail = await container1.read(
            placeDetailProvider(targetPlaceId).future,
          );
          expect(placeDetail.id, targetPlaceId);
          expect(placeDetail.isVerified, isTrue);
          _logStep(
            'Step 2 (Mở chi tiết POI): Opened "${placeDetail.name}" (place_id=${placeDetail.id}, destination=${placeDetail.destinationName}, dest_id=${placeDetail.destinationId})',
          );

          // 3. Chọn chuyến (tạo chuyến Hạ Long thực tế rồi chọn chuyến đó trong danh sách)
          final seededTrip =
              await container1.read(tripListProvider.notifier).createTrip(
                    CreateTripRequest(
                      title: 'Hành trình Hạ Long thực tế $stamp',
                      destinationId: placeDetail.destinationId ?? haLongDest.id,
                      description: 'Kiểm thử nghiệm thu lưu POI Hạ Long',
                    ),
                  );
          expect(seededTrip, isNotNull);
          await container1.read(tripListProvider.notifier).loadTrips();
          final selectedTrip = container1
              .read(tripListProvider)
              .trips
              .firstWhere((t) => t.id == seededTrip!.id);
          _logStep(
            'Step 3 (Chọn chuyến): Selected trip "${selectedTrip.title}" (trip_id=${selectedTrip.id})',
          );

          // 4. Lưu POI vào chuyến (POST /trips/:id/itinerary)
          final savedItem = await container1
              .read(tripRepositoryProvider)
              .addItineraryItem(
                selectedTrip.id,
                AddItineraryItemRequest(
                  dayNumber: 1,
                  activity: 'Tham quan ${placeDetail.name}',
                  placeId: placeDetail.id,
                  notes: placeDetail.hasAddress ? placeDetail.address : null,
                ),
              );
          expect(savedItem.placeId, targetPlaceId);
          _logStep(
            'Step 4 (Lưu): Persisted itinerary_item id=${savedItem.id}, day=${savedItem.orderIndex}, placeId=${savedItem.placeId}, activity="${savedItem.activity}"',
          );

          // 5. Đóng hoàn toàn ứng dụng (dispose toàn bộ Riverpod ProviderContainer trong RAM)
          homeSub.close();
          container1.dispose();
          _logStep(
            'Step 5 (Đóng app): Disposed Session #1 ProviderContainer (all in-memory state cleared; only SharedPreferences + PostgreSQL remain)',
          );

          // 6. Mở lại ứng dụng từ đầu (khôi phục JWT từ SharedPreferences -> mở danh sách chuyến -> mở chuyến vừa chọn)
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
            reason:
                'Cold reopen must restore authenticated session from SharedPreferences',
          );
          _logStep(
            'Step 6 (Mở lại app): Cold-started Session #2; session restored from SharedPreferences (AuthStatus.authenticated)',
          );

          await container2.read(tripListProvider.notifier).loadTrips();
          final reopenedTripSummary = container2
              .read(tripListProvider)
              .trips
              .firstWhere((t) => t.id == selectedTrip.id);
          _logStep(
            'Step 7a (Danh sách chuyến sau khi mở lại): Found trip "${reopenedTripSummary.title}" (trip_id=${reopenedTripSummary.id})',
          );

          await container2
              .read(tripDetailProvider.notifier)
              .loadTrip(reopenedTripSummary.id);
          final reopenedTrip = container2.read(tripDetailProvider).trip;
          expect(reopenedTrip, isNotNull);
          expect(reopenedTrip!.itineraries, isNotEmpty);

          final day1Items = reopenedTrip.itineraries
              .firstWhere((d) => d.dayNumber == 1)
              .items;
          final persistedPoiItem = day1Items.firstWhere(
            (i) => i.placeId == targetPlaceId,
          );
          expect(persistedPoiItem.id, savedItem.id);
          expect(persistedPoiItem.placeName, placeDetail.name);
          expect(persistedPoiItem.activity, 'Tham quan ${placeDetail.name}');

          _logStep(
            'Step 7b (Mở chuyến vừa chọn sau khi mở lại): VERIFIED persisted item id=${persistedPoiItem.id} -> activity="${persistedPoiItem.activity}", placeId=${persistedPoiItem.placeId}, placeName="${persistedPoiItem.placeName}"',
          );
        },
      );

      test(
        'Case 2 (Live): Chưa đăng nhập bấm lưu tại POI -> đăng nhập -> quay về đúng POI -> lưu vào chuyến',
        () async {
          // Khởi tạo phiên hoàn toàn chưa đăng nhập
          SharedPreferences.setMockInitialValues({});
          final container = _buildLiveContainer(baseUrl);
          addTearDown(container.dispose);
          final routerNotifier = container.read(routerNotifierProvider);
          await _waitForAuthSettled(container);
          expect(
              container.read(authProvider).status, AuthStatus.unauthenticated);

          // 1. Người dùng khách mở trang chi tiết POI Hạ Long công khai
          container.read(guestBrowseModeProvider.notifier).state = true;
          final guestPoi = await container.read(
            placeDetailProvider(targetPlaceId).future,
          );
          expect(guestPoi.id, targetPlaceId);
          _logStep(
            'Case 2 Step 1 (Khách xem POI): Loaded public POI "${guestPoi.name}" (/places/${guestPoi.id}) while unauthenticated',
          );

          // 2. Bấm Lưu khi chưa đăng nhập -> lưu target vào postLoginRedirectProvider & chuyển tới /login?redirect=...
          final intendedPoiRoute = '/places/${guestPoi.id}';
          container.read(postLoginRedirectProvider.notifier).state =
              intendedPoiRoute;
          final encodedLoginUrl =
              '/login?redirect=${Uri.encodeComponent(intendedPoiRoute)}';
          final parsedLoginUri = Uri.parse(encodedLoginUrl);
          _logStep(
            'Case 2 Step 2 (Bấm Lưu khi chưa đăng nhập): Redirected to $encodedLoginUrl',
          );

          // 3. Thực hiện đăng nhập thật qua POST /auth/login
          final loggedIn = await container
              .read(authProvider.notifier)
              .login(testEmail, testPassword);
          expect(loggedIn, isTrue);
          expect(container.read(authProvider).status, AuthStatus.authenticated);

          // 4. Xác minh RouterNotifier trả người dùng về ĐÚNG POI vừa xem
          final postLoginDestination =
              routerNotifier.resolvePostAuthDestination(
            queryRedirect: parsedLoginUri.queryParameters['redirect'],
          );
          expect(postLoginDestination, intendedPoiRoute);
          _logStep(
            'Case 2 Step 3 (Sau đăng nhập): RouterNotifier resolved post-login destination -> $postLoginDestination (exact POI)',
          );

          // 5. Lưu POI ngay sau khi quay lại đúng trang chi tiết POI
          await container.read(tripListProvider.notifier).loadTrips();
          final targetTrip = container.read(tripListProvider).trips.first;
          final postLoginSavedItem =
              await container.read(tripRepositoryProvider).addItineraryItem(
                    targetTrip.id,
                    AddItineraryItemRequest(
                      dayNumber: 2,
                      activity: 'Tham quan ${guestPoi.name} (sau đăng nhập)',
                      placeId: guestPoi.id,
                    ),
                  );
          expect(postLoginSavedItem.placeId, targetPlaceId);
          _logStep(
            'Case 2 Step 4 (Lưu sau đăng nhập): Saved item id=${postLoginSavedItem.id} on Day 2 of trip ${targetTrip.id} for placeId=${postLoginSavedItem.placeId}',
          );
        },
      );
    },
    skip:
        live ? false : 'set LIVE_HALONG_E2E=1 with PostgreSQL + NestJS running',
  );
}
