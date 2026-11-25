import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/features/auth/data/auth_models.dart';
import 'package:wanderai_mobile/features/auth/data/auth_repository.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/places/data/navigation_service.dart';
import 'package:wanderai_mobile/features/profile/data/profile_models.dart';
import 'package:wanderai_mobile/features/profile/data/profile_repository.dart';
import 'package:wanderai_mobile/features/safety/data/buddy_models.dart';
import 'package:wanderai_mobile/features/safety/data/buddy_repository.dart';
import 'package:wanderai_mobile/features/safety/data/safety_models.dart';
import 'package:wanderai_mobile/features/safety/data/safety_repository.dart';
import 'package:wanderai_mobile/features/safety/presentation/safety_and_buddies_screen.dart';
import 'package:wanderai_mobile/features/safety/providers/safety_provider.dart';

import 'location_navigation_test.dart' show FakeLocationService;

String _makeTestJwt(String userId) {
  final header = base64Url.encode(utf8.encode('{"alg":"HS256","typ":"JWT"}'));
  final payload = base64Url.encode(
    utf8.encode(jsonEncode({'sub': userId, 'email': '$userId@test.local'})),
  );
  return '$header.$payload.sig';
}

class _FakeSafetyNetworkClient implements SafetyNetworkClient {
  bool isOnline;
  int contactCreateCalls = 0;
  int contactDeleteCalls = 0;
  int checkinCreateCalls = 0;
  int emergencyEventCalls = 0;
  Completer<SafetyNetworkResult>? pendingCreateContactCompleter;
  Completer<SafetyNetworkResult>? pendingEmergencyCompleter;

  _FakeSafetyNetworkClient({this.isOnline = true});

  @override
  Future<bool> checkReachability() async => isOnline;

  @override
  Future<SafetyNetworkResult> createContact({
    required String name,
    required String phone,
    required String relation,
    required bool isAuthenticated,
  }) async {
    contactCreateCalls++;
    if (pendingCreateContactCompleter != null) {
      return pendingCreateContactCompleter!.future;
    }
    if (!isAuthenticated) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message:
            'Đã lưu cục bộ trên thiết bị (chưa đồng bộ máy chủ do chưa đăng nhập)',
      );
    }
    if (!isOnline) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.notSentOffline,
        message:
            'Chưa gửi được lên máy chủ do mất mạng — đã lưu cục bộ trên thiết bị',
        isOfflineError: true,
      );
    }
    return SafetyNetworkResult(
      status: SafetyNetworkSendStatus.sentOnline,
      message: 'Đã gửi thành công lên máy chủ',
      serverId: 'srv-contact-$contactCreateCalls',
    );
  }

  @override
  Future<SafetyNetworkResult> deleteContact({
    required String serverId,
    required bool isAuthenticated,
  }) async {
    contactDeleteCalls++;
    if (!isAuthenticated) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message: 'Đã xóa cục bộ',
      );
    }
    if (!isOnline) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.notSentOffline,
        message: 'Mất mạng',
        isOfflineError: true,
      );
    }
    return const SafetyNetworkResult(
      status: SafetyNetworkSendStatus.sentOnline,
      message: 'Đã đồng bộ xóa trên máy chủ',
    );
  }

  @override
  Future<SafetyNetworkResult> createCheckin({
    required double latitude,
    required double longitude,
    String? note,
    required bool isAuthenticated,
  }) async {
    checkinCreateCalls++;
    if (!isAuthenticated) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message:
            'Đã lưu cục bộ trên thiết bị (chưa đồng bộ máy chủ do chưa đăng nhập)',
      );
    }
    if (!isOnline) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.notSentOffline,
        message:
            'Chưa gửi được lên máy chủ do mất mạng — đã lưu cục bộ trên thiết bị',
        isOfflineError: true,
      );
    }
    return SafetyNetworkResult(
      status: SafetyNetworkSendStatus.sentOnline,
      message: 'Đã gửi thành công lên máy chủ',
      serverId: 'srv-checkin-$checkinCreateCalls',
    );
  }

  @override
  Future<SafetyNetworkResult> createEmergencyEvent({
    required double latitude,
    required double longitude,
    String? message,
    required bool isSandbox,
    required bool isAuthenticated,
  }) async {
    emergencyEventCalls++;
    if (pendingEmergencyCompleter != null) {
      return pendingEmergencyCompleter!.future;
    }
    if (!isAuthenticated) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.localOnly,
        message:
            'Đã lưu cục bộ trên thiết bị (chưa đồng bộ máy chủ do chưa đăng nhập)',
      );
    }
    if (!isOnline) {
      return const SafetyNetworkResult(
        status: SafetyNetworkSendStatus.notSentOffline,
        message:
            'Chưa gửi được lên máy chủ do mất mạng — đã lưu cục bộ trên thiết bị',
        isOfflineError: true,
      );
    }
    return SafetyNetworkResult(
      status: SafetyNetworkSendStatus.sentOnline,
      message: isSandbox
          ? 'Chế độ kiểm thử (Sandbox): Đã ghi nhận kiểm thử lên máy chủ'
          : 'Đã gửi thành công lên máy chủ',
      serverId: 'srv-event-$emergencyEventCalls',
    );
  }
}

class _StubBuddyRepo implements BuddyRepository {
  @override
  Future<BuddyCandidatesResponse> getCandidatesWithConsent({
    String? destinationId,
    int limit = 20,
  }) async =>
      const BuddyCandidatesResponse(isDiscoverable: false, items: []);

  @override
  Future<List<BuddyMatchRecord>> getMyMatches() async => const [];

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _Session {
  String? userId;
}

class _SwitchableAuthRepo extends AuthRepository {
  final _Session session;
  final Map<String, String> emailToUserId;
  _SwitchableAuthRepo(this.session, this.emailToUserId) : super(Dio());

  @override
  Future<bool> restoreSession() async => session.userId != null;

  @override
  Future<AuthTokens> login(LoginRequest request) async {
    final userId = emailToUserId[request.email]!;
    session.userId = userId;
    final token = _makeTestJwt(userId);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('access_token', token);
    await prefs.setString('refresh_token', 'refresh-$userId');
    return AuthTokens(accessToken: token, refreshToken: 'refresh-$userId');
  }

  @override
  Future<void> logout() async {
    session.userId = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
  }
}

class _SwitchableProfileRepo extends ProfileRepository {
  final _Session session;
  _SwitchableProfileRepo(this.session) : super(Dio());

  @override
  Future<UserProfile> getProfile() async {
    final id = session.userId;
    if (id == null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/users/me'),
        type: DioExceptionType.connectionError,
      );
    }
    return UserProfile(id: id, email: '$id@test.local');
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('W09-B Bundled Emergency Directory & Metadata Honesty', () {
    test(
        'assets/data/emergency_directory.json loads with verified national & UNKNOWN local metadata',
        () async {
      final repo = SafetyRepository();
      final bundle = await repo.loadEmergencyDirectory();

      expect(bundle.disclaimer, contains('không phải cơ quan điều phối cứu hộ'));
      expect(bundle.offlineTelecomNotice,
          contains('không cần kết nối Internet'));

      final byPhone = {for (final e in bundle.entries) e.phoneNumber: e};
      expect(byPhone.keys,
          containsAll(['112', '113', '114', '115', '111', '*8899', '1800556896', '1022']));

      for (final num in ['112', '113', '114', '115', '111']) {
        expect(byPhone[num]!.hoursStatus, MetadataEvidenceState.verified);
        expect(byPhone[num]!.chargeStatus, ChargeStatus.verifiedFree);
      }

      final dad = byPhone['*8899']!;
      expect(dad.hoursStatus, MetadataEvidenceState.unknown);
      expect(dad.chargeStatus, ChargeStatus.unknown);
      expect(dad.physicalAddress, '18 Hùng Vương, phường Hải Châu, Đà Nẵng');
      expect(dad.legacyHotline, '0236 3550 111');

      final han = byPhone['1800556896']!;
      expect(han.displayNumber, '1800 556 896');
      expect(han.hoursStatus, MetadataEvidenceState.unknown);
      expect(han.chargeStatus, ChargeStatus.verifiedFree);
      expect(han.secondaryPhone, '024 3926 1515');

      final sgn = byPhone['1022']!;
      expect(sgn.hoursStatus, MetadataEvidenceState.unknown);
      expect(sgn.chargeStatus, ChargeStatus.unknown);
      expect(sgn.dialNote, 'Nhánh 8 · Đường dây dự phòng: (+84) 28 3825 8558');
    });

    testWidgets(
        'Da Nang *8899 shows neutral label without 24/7 or Mien phi badges and omits legacy hotline dial button',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final net = _FakeSafetyNetworkClient(isOnline: false);

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            buddyRepositoryProvider.overrideWithValue(_StubBuddyRepo()),
            safetyNetworkClientProvider.overrideWithValue(net),
            guestBrowseModeProvider.overrideWith((ref) => true),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const SafetyAndBuddiesScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pumpAndSettle();

      final dadCard = find.byKey(const Key('safety_emergency_tile_*8899'));
      await tester.scrollUntilVisible(
        dadCard,
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pump();
      await tester.pumpAndSettle();

      expect(dadCard, findsOneWidget);
      expect(
        find.descendant(
          of: dadCard,
          matching: find.text('Thông tin hỗ trợ du khách'),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(of: dadCard, matching: find.text('24/7')),
        findsNothing,
      );
      expect(
        find.descendant(of: dadCard, matching: find.text('Miễn phí')),
        findsNothing,
      );
      expect(find.textContaining('0236 3550 111'), findsNothing);
    });
  });

  group('W09-B Case 1 & Case 2 — Confirmation, Single-Trigger Lock & Sandbox', () {
    testWidgets(
        'Case 1: tapping Cancel (Huy) on 113, 112, *8899, and SOS produces 0 dialer/network/log side effects',
        (tester) async {
      SharedPreferences.setMockInitialValues({
        'access_token': _makeTestJwt('user-case1'),
      });
      final net = _FakeSafetyNetworkClient(isOnline: true);
      final launchedUris = <Uri>[];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            buddyRepositoryProvider.overrideWithValue(_StubBuddyRepo()),
            safetyNetworkClientProvider.overrideWithValue(net),
            safetyInitialSandboxModeProvider.overrideWithValue(false),
            externalUriOpenerProvider.overrideWithValue((uri) async {
              launchedUris.add(uri);
              return true;
            }),
            authProvider.overrideWith(
              (ref) => AuthNotifier(
                _SwitchableAuthRepo(_Session()..userId = 'user-case1', {}),
              ),
            ),
            guestBrowseModeProvider.overrideWith((ref) => true),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const SafetyAndBuddiesScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pumpAndSettle();

      for (final targetKey in const [
        Key('safety_sos_button'),
        Key('safety_emergency_tile_112'),
        Key('safety_emergency_tile_113'),
        Key('safety_emergency_tile_*8899'),
      ]) {
        final finder = find.byKey(targetKey);
        await tester.scrollUntilVisible(
          finder,
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.ensureVisible(finder);
        await tester.pump();
      await tester.pumpAndSettle();
        await tester.tap(finder);
        await tester.pump();
      await tester.pumpAndSettle();

        expect(find.byKey(const Key('safety_confirm_dialog')), findsOneWidget);
        await tester.tap(find.byKey(const Key('safety_confirm_cancel')));
        await tester.pump();
      await tester.pumpAndSettle();
      }

      expect(launchedUris, isEmpty);
      expect(net.emergencyEventCalls, 0);
      expect(find.byKey(const Key('safety_event_log')), findsNothing);
    });

    testWidgets(
        'Case 2: Sandbox ON suppresses tel: dialing while recording sandbox event; Sandbox OFF invokes tel:113 once and reports online/offline SOS honestly',
        (tester) async {
      SharedPreferences.setMockInitialValues({
        'access_token': _makeTestJwt('user-case2'),
      });
      final net = _FakeSafetyNetworkClient(isOnline: true);
      final launchedUris = <Uri>[];
      final authRepo =
          _SwitchableAuthRepo(_Session()..userId = 'user-case2', {});

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            buddyRepositoryProvider.overrideWithValue(_StubBuddyRepo()),
            safetyNetworkClientProvider.overrideWithValue(net),
            externalUriOpenerProvider.overrideWithValue((uri) async {
              launchedUris.add(uri);
              return true;
            }),
            authProvider.overrideWith((ref) => AuthNotifier(authRepo)),
            guestBrowseModeProvider.overrideWith((ref) => true),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const SafetyAndBuddiesScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pumpAndSettle();

      // 1. Sandbox ON (default): tap 113 -> confirm -> 0 tel: launches, 1 sandbox event
      final tile113 = find.byKey(const Key('safety_emergency_tile_113'));
      await tester.scrollUntilVisible(
        tile113,
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(tile113);
      await tester.pump();
      await tester.pumpAndSettle();
      await tester.tap(tile113);
      await tester.pump();
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('safety_confirm_proceed')));
      await tester.pump();
      await tester.pumpAndSettle();

      expect(launchedUris, isEmpty);
      expect(
        find.byKey(const Key('safety_last_action_status')),
        findsOneWidget,
      );
      expect(find.textContaining('Sandbox'), findsWidgets);

      // 2. Toggle Sandbox OFF -> tap 113 -> confirm -> 1 tel:113 launch
      final sandboxSwitch = find.byKey(const Key('safety_sandbox_switch'));
      await tester.scrollUntilVisible(
        sandboxSwitch,
        -200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(sandboxSwitch);
      await tester.pump();
      await tester.pumpAndSettle();
      await tester.tap(sandboxSwitch);
      await tester.pump();
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        tile113,
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(tile113);
      await tester.pump();
      await tester.pumpAndSettle();
      await tester.tap(tile113);
      await tester.pump();
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('safety_confirm_proceed')));
      await tester.pump();
      await tester.pumpAndSettle();

      expect(launchedUris, [Uri.parse('tel:113')]);

      // 3. Online SOS -> reports sentOnline honestly
      final sosBtn = find.byKey(const Key('safety_sos_button'));
      await tester.scrollUntilVisible(
        sosBtn,
        -200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(sosBtn);
      await tester.pump();
      await tester.pumpAndSettle();
      await tester.tap(sosBtn);
      await tester.pump();
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('safety_confirm_proceed')));
      await tester.pump();
      await tester.pumpAndSettle();

      expect(net.emergencyEventCalls, 1);
      expect(
        find.descendant(
          of: find.byKey(const Key('safety_last_action_status')),
          matching: find.textContaining('Đã gửi thành công lên máy chủ'),
        ),
        findsOneWidget,
      );

      // 4. Offline SOS -> reports notSentOffline honestly (never claims sent)
      net.isOnline = false;
      await tester.tap(sosBtn);
      await tester.pump();
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('safety_confirm_proceed')));
      await tester.pump();
      await tester.pumpAndSettle();

      expect(net.emergencyEventCalls, 2);
      expect(
        find.descendant(
          of: find.byKey(const Key('safety_last_action_status')),
          matching: find.textContaining('Chưa gửi được lên máy chủ do mất mạng'),
        ),
        findsOneWidget,
      );
    });

    test(
        'Case 2 unit lock: concurrent triggerEmergencyAction calls while in-flight execute at most once',
        () async {
      SharedPreferences.setMockInitialValues({
        'access_token': _makeTestJwt('user-lock'),
      });
      final completer = Completer<SafetyNetworkResult>();
      final net = _FakeSafetyNetworkClient(isOnline: true)
        ..pendingEmergencyCompleter = completer;

      final container = ProviderContainer(
        overrides: [
          safetyNetworkClientProvider.overrideWithValue(net),
          authProvider.overrideWith(
            (ref) => AuthNotifier(
              _SwitchableAuthRepo(_Session()..userId = 'user-lock', {}),
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      await Future<void>.delayed(const Duration(milliseconds: 20));
      await container.read(safetyProvider.notifier).load();

      final firstCall =
          container.read(safetyProvider.notifier).triggerEmergencyAction(
                actionType: 'sos',
                targetNumber: 'SOS',
                targetLabel: 'SOS Lock Test',
              );
      // Wait 1 microtask for _ensureActiveScope to reach network call; lock is synchronous!
      final secondCall =
          container.read(safetyProvider.notifier).triggerEmergencyAction(
                actionType: 'sos',
                targetNumber: 'SOS',
                targetLabel: 'SOS Lock Test',
              );

      expect(await secondCall, isNull);
      completer.complete(
        const SafetyNetworkResult(
          status: SafetyNetworkSendStatus.sentOnline,
          message: 'Đã gửi',
        ),
      );
      final firstResult = await firstCall;
      expect(firstResult, isNotNull);
      expect(net.emergencyEventCalls, 1);
      expect(container.read(safetyProvider).events.length, 1);
    });
  });

  group('W09-B Case 3, Case 4 & Session Isolation', () {
    testWidgets(
        'Case 3: saved contact and check-in note persist across full container disposal and offline relaunch without /users/me',
        (tester) async {
      final token = _makeTestJwt('user-case3-halong');
      SharedPreferences.setMockInitialValues({
        'access_token': token,
        'refresh_token': 'refresh-case3',
      });

      // Phase 1: Online session saves contact + note
      final onlineNet = _FakeSafetyNetworkClient(isOnline: true);
      final container1 = ProviderContainer(
        overrides: [
          buddyRepositoryProvider.overrideWithValue(_StubBuddyRepo()),
          safetyNetworkClientProvider.overrideWithValue(onlineNet),
          authProvider.overrideWith(
            (ref) => AuthNotifier(
              _SwitchableAuthRepo(_Session()..userId = 'user-case3-halong', {}),
            ),
          ),
        ],
      );
      await tester.runAsync(() async {
        await Future<void>.delayed(const Duration(milliseconds: 20));
        await container1.read(safetyProvider.notifier).load();
        expect(
          await container1.read(safetyProvider.notifier).addContact(
                name: 'Minh Anh',
                phone: '0901234567',
                relation: 'family',
              ),
          isTrue,
        );
        await container1.read(safetyProvider.notifier).addCheckinNote(
              title: 'Check-in Hạ Long',
              note: 'Đã về khách sạn an toàn',
            );
      });
      container1.dispose();

      // Phase 2: Brand-new container + offline network + NO profile loaded
      final offlineNet = _FakeSafetyNetworkClient(isOnline: false);
      final container2 = ProviderContainer(
        overrides: [
          buddyRepositoryProvider.overrideWithValue(_StubBuddyRepo()),
          safetyNetworkClientProvider.overrideWithValue(offlineNet),
          authProvider.overrideWith(
            (ref) => AuthNotifier(
              _SwitchableAuthRepo(_Session()..userId = 'user-case3-halong', {}),
            ),
          ),
          guestBrowseModeProvider.overrideWith((ref) => true),
        ],
      );
      addTearDown(container2.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container2,
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const SafetyAndBuddiesScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 50)),
      );
      await tester.pumpAndSettle();

      // Switch to An toàn & SOS if authenticated default was Buddies
      if (find.byKey(const Key('safety_network_banner')).evaluate().isEmpty) {
        await tester.tap(find.text('An toàn & SOS'));
        await tester.pump();
      await tester.pumpAndSettle();
      }

      expect(find.byKey(const Key('safety_empty_offline_state')), findsNothing);
      expect(
        find.descendant(
          of: find.byKey(const Key('safety_network_banner')),
          matching: find.textContaining('Đang ngoại tuyến'),
        ),
        findsOneWidget,
      );

      final contactFinder = find.textContaining('Minh Anh · 0901234567');
      await tester.scrollUntilVisible(
        contactFinder,
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(contactFinder, findsOneWidget);

      final noteFinder = find.text('Đã về khách sạn an toàn');
      await tester.scrollUntilVisible(
        noteFinder,
        200,
        scrollable: find.byType(Scrollable).first,
      );
      expect(noteFinder, findsOneWidget);
    });

    testWidgets(
        'Case 4: first-launch offline with empty storage navigates to /safety in guest mode, shows explicit empty+offline state and bundled directory, and honestly reports failed SOS send',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      final offlineNet = _FakeSafetyNetworkClient(isOnline: false);

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            buddyRepositoryProvider.overrideWithValue(_StubBuddyRepo()),
            safetyNetworkClientProvider.overrideWithValue(offlineNet),
            safetyInitialSandboxModeProvider.overrideWithValue(false),
            locationServiceProvider.overrideWithValue(
              FakeLocationService(permission: LocationPermissionState.denied),
            ),
            authProvider.overrideWith(
              (ref) => AuthNotifier(_SwitchableAuthRepo(_Session(), {})),
            ),
          ],
          child: Consumer(
            builder: (context, ref, _) {
              final router = ref.watch(appRouterProvider);
              return MaterialApp.router(
                theme: AppTheme.lightTheme,
                routerConfig: router,
              );
            },
          ),
        ),
      );
      await tester.pump();
      await tester.pumpAndSettle();

      // Tap offline emergency shortcut on LoginScreen
      final safetyShortcut =
          find.byKey(const Key('login_emergency_safety_button'));
      await tester.ensureVisible(safetyShortcut);
      await tester.tap(safetyShortcut);
      await tester.pump();
      await tester.pumpAndSettle();
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 50)),
      );
      await tester.pumpAndSettle();

      // Must be on Safety tab without redirecting back to /login
      expect(find.byKey(const Key('safety_network_banner')), findsOneWidget);
      expect(
        find.descendant(
          of: find.byKey(const Key('safety_network_banner')),
          matching: find.textContaining('Đang ngoại tuyến'),
        ),
        findsOneWidget,
      );

      // Bundled directory entries visible offline
      expect(find.textContaining('112'), findsOneWidget);
      expect(find.textContaining('113'), findsOneWidget);
      expect(find.textContaining('114'), findsOneWidget);
      expect(find.textContaining('115'), findsOneWidget);
      expect(find.textContaining('111'), findsOneWidget);

      // Empty + offline personal state explicitly displayed
      final emptyOfflineFinder =
          find.byKey(const Key('safety_empty_offline_state'));
      await tester.scrollUntilVisible(
        emptyOfflineFinder,
        250,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pump();
      await tester.pumpAndSettle();
      expect(emptyOfflineFinder, findsOneWidget);
      expect(
        find.descendant(
          of: emptyOfflineFinder,
          matching: find.textContaining('ngoại tuyến'),
        ),
        findsWidgets,
      );

      // Triggering SOS while offline guest honestly reports localOnly (not sent to server)
      final sosBtn = find.byKey(const Key('safety_sos_button'));
      await tester.scrollUntilVisible(
        sosBtn,
        -250,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(sosBtn);
      await tester.pump();
      await tester.pumpAndSettle();
      await tester.tap(sosBtn);
      await tester.pump();
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('safety_confirm_proceed')));
      await tester.pump();
      await tester.pumpAndSettle();

      expect(
        find.descendant(
          of: find.byKey(const Key('safety_last_action_status')),
          matching: find.textContaining('chưa đồng bộ máy chủ'),
        ),
        findsOneWidget,
      );
    });

    test(
        'Session isolation & quota: User A safety data never leaks to User B and max 3 contacts is enforced',
        () async {
      final session = _Session()..userId = 'user-a';
      SharedPreferences.setMockInitialValues({
        'access_token': _makeTestJwt('user-a'),
      });
      final net = _FakeSafetyNetworkClient(isOnline: true);

      final container = ProviderContainer(
        overrides: [
          authRepositoryProvider.overrideWithValue(
            _SwitchableAuthRepo(
              session,
              {'a@test': 'user-a', 'b@test': 'user-b'},
            ),
          ),
          profileRepositoryProvider
              .overrideWithValue(_SwitchableProfileRepo(session)),
          safetyNetworkClientProvider.overrideWithValue(net),
        ],
      );
      addTearDown(container.dispose);

      container.read(routerNotifierProvider);
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(container.read(authProvider).status, AuthStatus.authenticated);

      await container.read(safetyProvider.notifier).load();
      expect(
        await container.read(safetyProvider.notifier).addContact(
              name: 'Liên hệ A1',
              phone: '0901',
              relation: 'family',
            ),
        isTrue,
      );
      expect(
        await container.read(safetyProvider.notifier).addContact(
              name: 'Liên hệ A2',
              phone: '0902',
              relation: 'friend',
            ),
        isTrue,
      );
      expect(
        await container.read(safetyProvider.notifier).addContact(
              name: 'Liên hệ A3',
              phone: '0903',
              relation: 'colleague',
            ),
        isTrue,
      );
      // 4th contact rejected locally by quota cap
      expect(
        await container.read(safetyProvider.notifier).addContact(
              name: 'Liên hệ A4',
              phone: '0904',
              relation: 'other',
            ),
        isFalse,
      );
      expect(container.read(safetyProvider).contacts.length, 3);
      expect(container.read(safetyProvider).errorMessage,
          contains('tối đa 3'));

      // Logout clears in-memory safety state immediately
      await container.read(authProvider.notifier).logout();
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(container.read(safetyProvider).contacts, isEmpty);

      // User B logs in -> completely isolated from User A
      expect(
        await container.read(authProvider.notifier).login('b@test', 'pw1234'),
        isTrue,
      );
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await container.read(safetyProvider.notifier).load();

      final bState = container.read(safetyProvider);
      expect(bState.scopeKey, 'user:user-b');
      expect(bState.contacts, isEmpty);
      expect(bState.notes, isEmpty);
      expect(bState.events, isEmpty);
    });

    testWidgets(
        'UI create/save flow for trusted contact and check-in note persists and renders',
        (tester) async {
      SharedPreferences.setMockInitialValues({
        'access_token': _makeTestJwt('user-ui-create'),
      });
      final net = _FakeSafetyNetworkClient(isOnline: true);

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            buddyRepositoryProvider.overrideWithValue(_StubBuddyRepo()),
            safetyNetworkClientProvider.overrideWithValue(net),
            authProvider.overrideWith(
              (ref) => AuthNotifier(
                _SwitchableAuthRepo(_Session()..userId = 'user-ui-create', {}),
              ),
            ),
            guestBrowseModeProvider.overrideWith((ref) => true),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const SafetyAndBuddiesScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pumpAndSettle();

      // Switch to An toàn & SOS
      if (find.byKey(const Key('safety_network_banner')).evaluate().isEmpty) {
        await tester.tap(find.text('An toàn & SOS'));
        await tester.pump();
        await tester.pumpAndSettle();
      }

      // Add trusted contact via UI dialog
      final addContactBtn = find.byKey(const Key('safety_add_contact_button'));
      await tester.scrollUntilVisible(
        addContactBtn,
        250,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(addContactBtn);
      await tester.tap(addContactBtn);
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('safety_contact_name_input')),
        'Bình An',
      );
      await tester.enterText(
        find.byKey(const Key('safety_contact_phone_input')),
        '0988777666',
      );
      await tester.tap(find.byKey(const Key('safety_contact_save_button')));
      await tester.pumpAndSettle();

      expect(net.contactCreateCalls, 1);
      expect(find.textContaining('Bình An · 0988777666'), findsOneWidget);

      // Add check-in note via UI dialog
      final addNoteBtn = find.byKey(const Key('safety_add_note_button'));
      await tester.ensureVisible(addNoteBtn);
      await tester.tap(addNoteBtn);
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('safety_note_body_input')),
        'Đang ở Bến tàu Tuần Châu',
      );
      await tester.tap(find.byKey(const Key('safety_note_save_button')));
      await tester.pumpAndSettle();

      expect(net.checkinCreateCalls, 1);
      expect(find.text('Đang ở Bến tàu Tuần Châu'), findsOneWidget);
    });
  });

  group('W09-B Iteration 2 Regression Hardening', () {
    test(
        'Mid-flight addContact resolving after logout/user switch never leaks into User B or overwrites User A store',
        () async {
      final session = _Session()..userId = 'user-a';
      SharedPreferences.setMockInitialValues({
        'access_token': _makeTestJwt('user-a'),
      });
      final completerA = Completer<SafetyNetworkResult>();
      final net = _FakeSafetyNetworkClient(isOnline: true)
        ..pendingCreateContactCompleter = completerA;

      final container = ProviderContainer(
        overrides: [
          authRepositoryProvider.overrideWithValue(
            _SwitchableAuthRepo(
              session,
              {'a@test': 'user-a', 'b@test': 'user-b'},
            ),
          ),
          profileRepositoryProvider
              .overrideWithValue(_SwitchableProfileRepo(session)),
          safetyNetworkClientProvider.overrideWithValue(net),
        ],
      );
      addTearDown(container.dispose);

      container.read(routerNotifierProvider);
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await container.read(safetyProvider.notifier).load();

      final inFlightAdd = container.read(safetyProvider.notifier).addContact(
            name: 'User A Late Contact',
            phone: '0901111222',
            relation: 'family',
          );
      await Future<void>.delayed(const Duration(milliseconds: 20));

      // Logout User A and login User B before User A's createContact resolves
      await container.read(authProvider.notifier).logout();
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(
        await container.read(authProvider.notifier).login('b@test', 'pw1234'),
        isTrue,
      );
      await Future<void>.delayed(const Duration(milliseconds: 20));

      net.pendingCreateContactCompleter = null;
      await container.read(safetyProvider.notifier).load();
      expect(
        await container.read(safetyProvider.notifier).addContact(
              name: 'User B Own Contact',
              phone: '0909888777',
              relation: 'friend',
            ),
        isTrue,
      );

      // Late User A response arrives now
      completerA.complete(
        const SafetyNetworkResult(
          status: SafetyNetworkSendStatus.sentOnline,
          message: 'Đã gửi thành công lên máy chủ',
          serverId: 'srv-a-late',
        ),
      );
      expect(await inFlightAdd, isFalse);

      final bState = container.read(safetyProvider);
      expect(bState.scopeKey, 'user:user-b');
      expect(bState.contacts.map((c) => c.name).toList(), ['User B Own Contact']);
      expect(bState.lastActionBannerMessage, isNot(contains('User A Late Contact')));

      // User A's persisted store must remain unpolluted (no mixed User B data)
      final repo = SafetyRepository();
      final userAStore = await repo.loadUserStore('user:user-a');
      expect(userAStore.contacts, isEmpty);
    });

    test(
        'Mid-flight triggerEmergencyAction resolving after resetForAuthTransition never leaks and never clears new session lock',
        () async {
      final session = _Session()..userId = 'user-a';
      SharedPreferences.setMockInitialValues({
        'access_token': _makeTestJwt('user-a'),
      });
      final completerA = Completer<SafetyNetworkResult>();
      final completerNext = Completer<SafetyNetworkResult>();
      final net = _FakeSafetyNetworkClient(isOnline: true)
        ..pendingEmergencyCompleter = completerA;

      final container = ProviderContainer(
        overrides: [
          authRepositoryProvider.overrideWithValue(
            _SwitchableAuthRepo(session, {'a@test': 'user-a'}),
          ),
          profileRepositoryProvider
              .overrideWithValue(_SwitchableProfileRepo(session)),
          safetyNetworkClientProvider.overrideWithValue(net),
        ],
      );
      addTearDown(container.dispose);

      container.read(routerNotifierProvider);
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await container.read(safetyProvider.notifier).load();

      // Start User A SOS trigger
      final triggerA =
          container.read(safetyProvider.notifier).triggerEmergencyAction(
                actionType: 'sos',
                targetNumber: 'SOS',
                targetLabel: 'User A SOS',
              );
      await Future<void>.delayed(const Duration(milliseconds: 20));

      // Logout calls resetForAuthTransition() on the same mounted SafetyNotifier
      await container.read(authProvider.notifier).logout();
      await Future<void>.delayed(const Duration(milliseconds: 20));

      // New guest session starts a new emergency trigger
      net.pendingEmergencyCompleter = completerNext;
      final triggerNext =
          container.read(safetyProvider.notifier).triggerEmergencyAction(
                actionType: 'sos',
                targetNumber: 'SOS',
                targetLabel: 'Guest Next SOS',
              );
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(container.read(safetyProvider).isTriggerInFlight, isTrue);

      // User A's late response resolves now; must NOT leak or unlock Guest Next SOS
      completerA.complete(
        const SafetyNetworkResult(
          status: SafetyNetworkSendStatus.sentOnline,
          message: 'Đã gửi thành công lên máy chủ',
          serverId: 'srv-a-sos',
        ),
      );
      expect(await triggerA, isNull);
      expect(container.read(safetyProvider).isTriggerInFlight, isTrue);
      expect(container.read(safetyProvider).events, isEmpty);

      // Duplicate trigger while Guest Next SOS is still in-flight must still be blocked
      final duplicateNext =
          await container.read(safetyProvider.notifier).triggerEmergencyAction(
                actionType: 'sos',
                targetNumber: 'SOS',
                targetLabel: 'Guest Duplicate SOS',
              );
      expect(duplicateNext, isNull);

      // Complete Guest Next SOS
      completerNext.complete(
        const SafetyNetworkResult(
          status: SafetyNetworkSendStatus.localOnly,
          message: 'Đã lưu cục bộ',
        ),
      );
      final nextResult = await triggerNext;
      expect(nextResult, isNotNull);
      expect(nextResult!.targetLabel, 'Guest Next SOS');
      expect(container.read(safetyProvider).isTriggerInFlight, isFalse);
      expect(container.read(safetyProvider).events.length, 1);
      expect(
        container.read(safetyProvider).events.single.targetLabel,
        'Guest Next SOS',
      );
    });

    test(
        'removeContact on server-synced contact reports notSentOffline when offline and sentOnline when online',
        () async {
      SharedPreferences.setMockInitialValues({
        'access_token': _makeTestJwt('user-remove-status'),
      });
      final net = _FakeSafetyNetworkClient(isOnline: true);

      final container = ProviderContainer(
        overrides: [
          safetyNetworkClientProvider.overrideWithValue(net),
          authProvider.overrideWith(
            (ref) => AuthNotifier(
              _SwitchableAuthRepo(_Session()..userId = 'user-remove-status', {}),
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      await Future<void>.delayed(const Duration(milliseconds: 20));
      await container.read(safetyProvider.notifier).load();

      expect(
        await container.read(safetyProvider.notifier).addContact(
              name: 'Contact 1',
              phone: '0901000001',
              relation: 'family',
            ),
        isTrue,
      );
      expect(
        await container.read(safetyProvider.notifier).addContact(
              name: 'Contact 2',
              phone: '0901000002',
              relation: 'friend',
            ),
        isTrue,
      );

      final contacts = container.read(safetyProvider).contacts;
      expect(contacts.length, 2);
      expect(contacts[0].serverId, isNotNull);
      expect(contacts[1].serverId, isNotNull);

      // Delete first contact while offline -> honest notSentOffline banner
      net.isOnline = false;
      expect(
        await container
            .read(safetyProvider.notifier)
            .removeContact(contacts[0].id),
        isTrue,
      );
      final afterOfflineDelete = container.read(safetyProvider);
      expect(net.contactDeleteCalls, 1);
      expect(afterOfflineDelete.isOffline, isTrue);
      expect(
        afterOfflineDelete.lastActionStatus,
        SafetyNetworkSendStatus.notSentOffline,
      );
      expect(afterOfflineDelete.lastActionBannerMessage, contains('Mất mạng'));

      // Delete second contact while online -> sentOnline banner
      net.isOnline = true;
      expect(
        await container
            .read(safetyProvider.notifier)
            .removeContact(contacts[1].id),
        isTrue,
      );
      final afterOnlineDelete = container.read(safetyProvider);
      expect(net.contactDeleteCalls, 2);
      expect(afterOnlineDelete.contacts, isEmpty);
      expect(
        afterOnlineDelete.lastActionStatus,
        SafetyNetworkSendStatus.sentOnline,
      );
      expect(
        afterOnlineDelete.lastActionBannerMessage,
        contains('Đã đồng bộ xóa trên máy chủ'),
      );
    });

    test(
        'Concurrent addContact calls at 2/3 contacts enforce max-3 without lost update',
        () async {
      SharedPreferences.setMockInitialValues({
        'access_token': _makeTestJwt('user-concurrent-contacts'),
      });
      final net = _FakeSafetyNetworkClient(isOnline: true);

      final container = ProviderContainer(
        overrides: [
          safetyNetworkClientProvider.overrideWithValue(net),
          authProvider.overrideWith(
            (ref) => AuthNotifier(
              _SwitchableAuthRepo(
                _Session()..userId = 'user-concurrent-contacts',
                {},
              ),
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      await Future<void>.delayed(const Duration(milliseconds: 20));
      await container.read(safetyProvider.notifier).load();

      expect(
        await container.read(safetyProvider.notifier).addContact(
              name: 'C1',
              phone: '0901',
              relation: 'family',
            ),
        isTrue,
      );
      expect(
        await container.read(safetyProvider.notifier).addContact(
              name: 'C2',
              phone: '0902',
              relation: 'friend',
            ),
        isTrue,
      );

      final pending = Completer<SafetyNetworkResult>();
      net.pendingCreateContactCompleter = pending;

      final f3 = container.read(safetyProvider.notifier).addContact(
            name: 'C3',
            phone: '0903',
            relation: 'colleague',
          );
      final f4 = container.read(safetyProvider.notifier).addContact(
            name: 'C4',
            phone: '0904',
            relation: 'other',
          );

      await Future<void>.delayed(const Duration(milliseconds: 20));
      pending.complete(
        const SafetyNetworkResult(
          status: SafetyNetworkSendStatus.sentOnline,
          message: 'Đã gửi thành công lên máy chủ',
          serverId: 'srv-3',
        ),
      );

      final results = await Future.wait([f3, f4]);
      expect(results, [true, false]);
      expect(net.contactCreateCalls, 3);
      expect(
        container.read(safetyProvider).contacts.map((c) => c.name).toList(),
        ['C1', 'C2', 'C3'],
      );
    });

    test(
        'Trusted contact phone with spaces strips whitespace in tel: URI while keeping display format',
        () async {
      SharedPreferences.setMockInitialValues({});
      final net = _FakeSafetyNetworkClient(isOnline: false);
      final launchedUris = <Uri>[];

      final container = ProviderContainer(
        overrides: [
          safetyNetworkClientProvider.overrideWithValue(net),
          safetyInitialSandboxModeProvider.overrideWithValue(false),
          externalUriOpenerProvider.overrideWithValue((uri) async {
            launchedUris.add(uri);
            return true;
          }),
        ],
      );
      addTearDown(container.dispose);

      await container.read(safetyProvider.notifier).load();
      expect(
        await container.read(safetyProvider.notifier).addContact(
              name: 'Gia đình',
              phone: '0901 234 567',
              relation: 'family',
            ),
        isTrue,
      );

      final entry =
          await container.read(safetyProvider.notifier).triggerEmergencyAction(
                actionType: 'dial',
                targetNumber: '0901 234 567',
                targetLabel: 'Gia đình',
              );

      expect(entry, isNotNull);
      expect(launchedUris, [Uri.parse('tel:0901234567')]);
      expect(entry!.targetNumber, '0901 234 567');
      expect(entry.statusMessage, contains('0901 234 567'));
    });
  });
}
