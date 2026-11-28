import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/features/notifications/data/notification_models.dart';
import 'package:wanderai_mobile/features/notifications/data/notification_repository.dart';
import 'package:wanderai_mobile/features/notifications/presentation/notifications_screen.dart';
import 'package:wanderai_mobile/features/notifications/presentation/trip_invite_detail_screen.dart';
import 'package:wanderai_mobile/features/notifications/presentation/widgets/notification_bell_button.dart';
import 'package:wanderai_mobile/features/notifications/providers/notification_provider.dart';
import 'package:wanderai_mobile/features/trips/data/trip_models.dart';
import 'package:wanderai_mobile/features/trips/data/trip_repository.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_detail_screen.dart';
import 'package:wanderai_mobile/features/trips/providers/trip_provider.dart';

class _FakeNotificationRepo extends NotificationRepository {
  List<AppNotificationModel> notifications;
  Map<String, TripInviteDetailModel> invitesById;
  int getNotificationsCalls = 0;

  _FakeNotificationRepo({
    required this.notifications,
    required this.invitesById,
  }) : super(Dio());

  int get _computedUnread =>
      notifications.where((n) => !n.isRead).length;

  @override
  Future<NotificationsListResult> getNotifications({int limit = 50}) async {
    getNotificationsCalls++;
    return NotificationsListResult(
      items: List<AppNotificationModel>.from(notifications),
      unreadCount: _computedUnread,
    );
  }

  @override
  Future<int> markRead(String notificationId) async {
    notifications = notifications
        .map((n) => n.id == notificationId ? n.copyWith(isRead: true) : n)
        .toList();
    return _computedUnread;
  }

  @override
  Future<TripInviteDetailModel> getTripInviteDetail(String inviteId) async {
    return invitesById[inviteId]!;
  }

  @override
  Future<({TripInviteDetailModel invite, String tripId})> acceptTripInvite(
    String inviteId,
  ) async {
    final cur = invitesById[inviteId]!;
    final updated = TripInviteDetailModel(
      id: cur.id,
      tripId: cur.tripId,
      tripTitle: cur.tripTitle,
      tripDescription: cur.tripDescription,
      destinationName: cur.destinationName,
      startDate: cur.startDate,
      endDate: cur.endDate,
      status: TripInviteStatus.accepted,
      notificationId: cur.notificationId,
      inviterId: cur.inviterId,
      inviterDisplayName: cur.inviterDisplayName,
      inviteeId: cur.inviteeId,
      inviteeDisplayName: cur.inviteeDisplayName,
      createdAt: cur.createdAt,
      respondedAt: DateTime.now(),
    );
    invitesById[inviteId] = updated;
    notifications = notifications.map((n) {
      if (n.effectiveInviteId == inviteId) {
        return n.copyWith(
          isRead: true,
          tripInvite: NotificationTripInviteMeta(
            inviteId: inviteId,
            tripId: cur.tripId,
            tripTitle: cur.tripTitle,
            destinationName: cur.destinationName,
            inviterId: cur.inviterId,
            inviterDisplayName: cur.inviterDisplayName,
            status: TripInviteStatus.accepted,
          ),
        );
      }
      return n;
    }).toList();
    return (invite: updated, tripId: cur.tripId);
  }
}

class _FakeTripRepo extends TripRepository {
  final Map<String, TripModel> trips;
  _FakeTripRepo(this.trips) : super(Dio());

  @override
  Future<List<TripModel>> getMyTrips() async => trips.values.toList();

  @override
  Future<TripModel> getTripDetail(String id) async => trips[id]!;
}

void main() {
  group('In-App Trip Invite Notifications Flow', () {
    testWidgets(
      '1. Bell badge shows unread count, deduplicates repeated invite items, opens invite -> accepts -> navigates into exact TripDetailScreen',
      (tester) async {
        const tripId = 'trip-halong-123';
        const inviteId = 'inv-halong-001';
        final now = DateTime.utc(2026, 11, 28, 9, 0);

        final fakeRepo = _FakeNotificationRepo(
          notifications: [
            AppNotificationModel(
              id: 'notif-1',
              userId: 'user-b',
              type: 'TRIP_INVITE',
              title: 'Lời mời tham gia chuyến đi',
              body: 'Chủ chuyến A mời bạn tham gia chuyến "Khám phá Hạ Long 3N2Đ".',
              isRead: false,
              createdAt: now,
              tripInvite: const NotificationTripInviteMeta(
                inviteId: inviteId,
                tripId: tripId,
                tripTitle: 'Khám phá Hạ Long 3N2Đ',
                destinationName: 'Hạ Long',
                inviterId: 'user-a',
                inviterDisplayName: 'Chủ chuyến A',
                status: TripInviteStatus.pending,
              ),
            ),
            // Simulated accidental duplicate payload sharing same inviteId -> deduplicated
            AppNotificationModel(
              id: 'notif-1-dup',
              userId: 'user-b',
              type: 'TRIP_INVITE',
              title: 'Lời mời tham gia chuyến đi',
              body: 'Chủ chuyến A mời bạn tham gia chuyến "Khám phá Hạ Long 3N2Đ".',
              isRead: false,
              createdAt: now,
              tripInvite: const NotificationTripInviteMeta(
                inviteId: inviteId,
                tripId: tripId,
                tripTitle: 'Khám phá Hạ Long 3N2Đ',
                destinationName: 'Hạ Long',
                inviterId: 'user-a',
                inviterDisplayName: 'Chủ chuyến A',
                status: TripInviteStatus.pending,
              ),
            ),
          ],
          invitesById: {
            inviteId: TripInviteDetailModel(
              id: inviteId,
              tripId: tripId,
              tripTitle: 'Khám phá Hạ Long 3N2Đ',
              tripDescription: 'Du thuyền và hang Sửng Sốt',
              destinationName: 'Hạ Long',
              status: TripInviteStatus.pending,
              notificationId: 'notif-1',
              inviterId: 'user-a',
              inviterDisplayName: 'Chủ chuyến A',
              inviteeId: 'user-b',
              inviteeDisplayName: 'Đồng hành B',
              createdAt: now,
            ),
          },
        );
        // Server unreadCount reflects single canonical notification
        fakeRepo.notifications = [fakeRepo.notifications.first];

        final fakeTripRepo = _FakeTripRepo({
          tripId: const TripModel(
            id: tripId,
            userId: 'user-a',
            title: 'Khám phá Hạ Long 3N2Đ',
            destinationName: 'Hạ Long',
            memberCount: 2,
          ),
        });

        final router = GoRouter(
          initialLocation: '/',
          routes: [
            GoRoute(
              path: '/',
              builder: (_, __) => NotificationAutoSyncHost(
                enabled: true,
                child: Scaffold(
                  appBar: AppBar(
                    title: const Text('Trang chủ'),
                    actions: const [NotificationBellButton()],
                  ),
                  body: const Center(child: Text('HOME_BODY')),
                ),
              ),
            ),
            GoRoute(
              path: '/notifications',
              builder: (_, __) => const NotificationsScreen(),
            ),
            GoRoute(
              path: '/trips/invites/:inviteId',
              builder: (_, st) => TripInviteDetailScreen(
                inviteId: st.pathParameters['inviteId']!,
              ),
            ),
            GoRoute(
              path: '/trips/:id',
              builder: (_, st) => TripDetailScreen(
                tripId: st.pathParameters['id']!,
              ),
            ),
          ],
        );

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              notificationRepositoryProvider.overrideWithValue(fakeRepo),
              notificationPollIntervalProvider
                  .overrideWithValue(const Duration(seconds: 2)),
              tripRepositoryProvider.overrideWithValue(fakeTripRepo),
            ],
            child: MaterialApp.router(
              theme: AppTheme.lightTheme,
              routerConfig: router,
            ),
          ),
        );
        await tester.pumpAndSettle();

        // Unread badge shows "1"
        expect(find.byKey(const Key('app_notification_unread_badge')), findsOneWidget);
        expect(find.text('1'), findsOneWidget);

        // Tap bell -> open NotificationsScreen -> shows exact 1 item
        await tester.tap(find.byKey(const Key('app_notification_bell_button')));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('notification_item_notif-1')), findsOneWidget);
        expect(find.text('Chờ phản hồi'), findsOneWidget);

        // Tap notification -> opens TripInviteDetailScreen
        await tester.tap(find.byKey(const Key('notification_item_notif-1')));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('trip_invite_detail_trip_title')), findsOneWidget);
        expect(find.text('Khám phá Hạ Long 3N2Đ'), findsOneWidget);

        // Tap Accept -> navigates directly to TripDetailScreen of trip-halong-123
        await tester.tap(find.byKey(const Key('trip_invite_accept_button')));
        await tester.pumpAndSettle();
        expect(find.text('Lịch trình chi tiết'), findsOneWidget);
        expect(find.text('Khám phá Hạ Long 3N2Đ'), findsWidgets);

        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump();
      },
    );

    testWidgets(
      '2. Revoked invite displays Đã thu hồi state clearly and hides Accept button',
      (tester) async {
        const inviteId = 'inv-revoked-999';
        final now = DateTime.utc(2026, 11, 28, 10, 0);

        final fakeRepo = _FakeNotificationRepo(
          notifications: [
            AppNotificationModel(
              id: 'notif-revoked',
              userId: 'user-b',
              type: 'TRIP_INVITE',
              title: 'Lời mời tham gia chuyến đi',
              body: 'Chủ chuyến A mời bạn tham gia chuyến "Chuyến Đà Nẵng".',
              isRead: false,
              createdAt: now,
              tripInvite: const NotificationTripInviteMeta(
                inviteId: inviteId,
                tripId: 'trip-dn',
                tripTitle: 'Chuyến Đà Nẵng',
                inviterId: 'user-a',
                inviterDisplayName: 'Chủ chuyến A',
                status: TripInviteStatus.revoked,
              ),
            ),
          ],
          invitesById: {
            inviteId: TripInviteDetailModel(
              id: inviteId,
              tripId: 'trip-dn',
              tripTitle: 'Chuyến Đà Nẵng',
              status: TripInviteStatus.revoked,
              notificationId: 'notif-revoked',
              inviterId: 'user-a',
              inviterDisplayName: 'Chủ chuyến A',
              inviteeId: 'user-b',
              inviteeDisplayName: 'Đồng hành B',
              createdAt: now,
              revokedAt: now,
            ),
          },
        );

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              notificationRepositoryProvider.overrideWithValue(fakeRepo),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              home: const TripInviteDetailScreen(inviteId: inviteId),
            ),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Đã thu hồi'), findsOneWidget);
        expect(find.byKey(const Key('trip_invite_revoked_banner')), findsOneWidget);
        expect(find.byKey(const Key('trip_invite_accept_button')), findsNothing);
      },
    );

    testWidgets(
      '3. NotificationAutoSyncHost polls on 2s cycle to surface new invite badge and stops polling after unmount',
      (tester) async {
        final now = DateTime.utc(2026, 11, 28, 11, 0);
        final fakeRepo = _FakeNotificationRepo(
          notifications: [],
          invitesById: {},
        );

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              notificationRepositoryProvider.overrideWithValue(fakeRepo),
              notificationPollIntervalProvider
                  .overrideWithValue(kDefaultNotificationPollInterval),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              home: NotificationAutoSyncHost(
                enabled: true,
                child: Scaffold(
                  appBar: AppBar(actions: const [NotificationBellButton()]),
                ),
              ),
            ),
          ),
        );
        await tester.pump();
        expect(fakeRepo.getNotificationsCalls, 1);
        expect(find.byKey(const Key('app_notification_unread_badge')), findsNothing);

        // Server receives invite from A -> next 2s poll updates B's unread badge 0 -> 1
        fakeRepo.notifications = [
          AppNotificationModel(
            id: 'notif-auto-1',
            userId: 'user-b',
            type: 'TRIP_INVITE',
            title: 'Lời mời tham gia chuyến đi',
            body: 'A mời bạn vào chuyến Huế.',
            isRead: false,
            createdAt: now,
          ),
        ];

        await tester.pump(const Duration(seconds: 2));
        await tester.pump();
        expect(fakeRepo.getNotificationsCalls, 2);
        expect(find.byKey(const Key('app_notification_unread_badge')), findsOneWidget);
        expect(find.text('1'), findsOneWidget);

        // Unmount host -> advance 10s (5 cycles) -> zero extra requests
        final callsAtUnmount = fakeRepo.getNotificationsCalls;
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump(const Duration(seconds: 10));
        expect(fakeRepo.getNotificationsCalls, callsAtUnmount);
      },
    );
  });
}
