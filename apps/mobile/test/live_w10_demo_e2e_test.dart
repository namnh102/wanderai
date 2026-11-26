@TestOn('vm')
library;

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/groups/data/group_expense_models.dart';
import 'package:wanderai_mobile/features/groups/data/group_itinerary_models.dart';
import 'package:wanderai_mobile/features/groups/data/group_models.dart';
import 'package:wanderai_mobile/features/groups/data/group_repository.dart';
import 'package:wanderai_mobile/features/groups/presentation/group_detail_screen.dart';
import 'package:wanderai_mobile/features/groups/providers/group_expense_provider.dart';
import 'package:wanderai_mobile/features/groups/providers/group_itinerary_provider.dart';
import 'package:wanderai_mobile/features/groups/providers/group_provider.dart';
import 'package:wanderai_mobile/features/profile/data/profile_models.dart';
import 'package:wanderai_mobile/features/profile/data/profile_repository.dart';
import 'package:wanderai_mobile/features/trips/data/trip_models.dart';

class _LiveFetchedW10GroupRepo extends GroupRepository {
  final GroupModel preloadedGroup;
  final ExpenseListModel preloadedExpenses;
  final SettlementPlanModel preloadedPlan;

  _LiveFetchedW10GroupRepo(
    super.dio, {
    required this.preloadedGroup,
    required this.preloadedExpenses,
    required this.preloadedPlan,
  });

  @override
  Future<GroupModel> getGroup(String id) async => preloadedGroup;

  @override
  Future<ExpenseListModel> listExpenses(String groupId) async =>
      preloadedExpenses;

  @override
  Future<SettlementPlanModel> getSettlementPlan(String groupId) async =>
      preloadedPlan;
}

class _LiveFetchedProfileRepo extends ProfileRepository {
  final UserProfile preloadedProfile;
  _LiveFetchedProfileRepo(super.dio, this.preloadedProfile);

  @override
  Future<UserProfile> getProfile() async => preloadedProfile;
}

ProviderContainer _buildLiveContainer(String baseUrl) {
  return ProviderContainer(
    overrides: [
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
  HttpOverrides.global = null;

  final live = Platform.environment['LIVE_W10_DEMO_E2E'] == '1';
  final baseUrl =
      Platform.environment['LIVE_API_BASE_URL'] ?? 'http://127.0.0.1:3000';

  group('W10 Live End-to-End 3-Actor Demo Journey (Flutter -> NestJS -> PostgreSQL)', () {
    late String groupId;
    late String u1Id;
    late String u2Id;
    late String u3Id;
    late String u3AccessToken;
    late String u3RefreshToken;

    test(
      'Demo Step 1..6: 3-role setup (U1 owner, U2 dual via POST /trips/:id/members, U3 GroupMember-only) -> U3 403 Trip gate -> U2 propose & vote switch/withdraw -> U1 reorder -> 100.000/3 VND split -> U1 admin debtor blocked 403 -> U3 creditor confirms settlement',
      () async {
        final stamp = DateTime.now().millisecondsSinceEpoch;
        const pass = 'W10Demo#2026';

        // Register U2 (Dual-role member)
        SharedPreferences.setMockInitialValues({});
        final c2 = _buildLiveContainer(baseUrl);
        c2.read(routerNotifierProvider);
        await _waitForAuthSettled(c2);
        final u2Email = 'w10_demo_u2_$stamp@gomate.vn';
        expect(
          await c2
              .read(authProvider.notifier)
              .register('Thành Viên Đủ Quyền U2', u2Email, pass),
          isTrue,
        );
        final u2Me = await c2.read(apiClientProvider).get('/users/me');
        u2Id = u2Me.data['data']['id'] as String;
        final u2Prefs = await SharedPreferences.getInstance();
        final u2Access = u2Prefs.getString('access_token')!;
        final u2Refresh = u2Prefs.getString('refresh_token')!;

        // Register U3 (GroupMember-only)
        SharedPreferences.setMockInitialValues({});
        final c3 = _buildLiveContainer(baseUrl);
        c3.read(routerNotifierProvider);
        await _waitForAuthSettled(c3);
        final u3Email = 'w10_demo_u3_$stamp@gomate.vn';
        expect(
          await c3
              .read(authProvider.notifier)
              .register('Thành Viên Chỉ Nhóm U3', u3Email, pass),
          isTrue,
        );
        final u3Me = await c3.read(apiClientProvider).get('/users/me');
        u3Id = u3Me.data['data']['id'] as String;
        final u3Prefs = await SharedPreferences.getInstance();
        u3AccessToken = u3Prefs.getString('access_token')!;
        u3RefreshToken = u3Prefs.getString('refresh_token')!;

        // Register U1 (Trip Owner & Group Admin)
        SharedPreferences.setMockInitialValues({});
        final c1 = _buildLiveContainer(baseUrl);
        c1.read(routerNotifierProvider);
        await _waitForAuthSettled(c1);
        final u1Email = 'w10_demo_u1_$stamp@gomate.vn';
        expect(
          await c1
              .read(authProvider.notifier)
              .register('Chủ Chuyến U1', u1Email, pass),
          isTrue,
        );
        final u1Me = await c1.read(apiClientProvider).get('/users/me');
        u1Id = u1Me.data['data']['id'] as String;
        final u1Prefs = await SharedPreferences.getInstance();
        final u1Access = u1Prefs.getString('access_token')!;
        final u1Refresh = u1Prefs.getString('refresh_token')!;

        // U1 creates Trip & grants TripMember ONLY to U2 via POST /trips/:id/members
        final tripRes = await c1.read(apiClientProvider).post(
          '/trips',
          data: {'title': 'Hành Trình Demo Hạ Long W10'},
        );
        final tripId = tripRes.data['data']['id'] as String;
        await c1.read(apiClientProvider).post(
          '/trips/$tripId/members',
          data: {'email': u2Email},
        );

        // U1 creates Group linked to Trip & adds both U2 and U3 to Group
        final createdGroup = await c1
            .read(groupListProvider.notifier)
            .createGroup(
              CreateGroupRequest(
                name: 'Nhóm Demo Hạ Long W10',
                description: 'Kiểm chứng 3 vai trò W10',
                tripId: tripId,
              ),
            );
        expect(createdGroup, isNotNull);
        groupId = createdGroup!.id;
        expect(
          await c1.read(groupDetailProvider.notifier).addMember(groupId, u2Id),
          isTrue,
        );
        expect(
          await c1.read(groupDetailProvider.notifier).addMember(groupId, u3Id),
          isTrue,
        );
        // ignore: avoid_print
        print('[W10-DEMO] Step 1 PASS: Group=$groupId Trip=$tripId U1=$u1Id U2=$u2Id U3=$u3Id');

        // U1 proposes Item 1
        expect(
          await c1.read(groupItineraryProvider.notifier).proposeItem(
                groupId,
                const ProposeGroupItineraryItemRequest(
                  dayNumber: 1,
                  activity: 'Tháp Đồng Hồ Hạ Long',
                  clientRequestId: 'demo-item-1',
                ),
              ),
          isTrue,
        );

        // Switch to U3 (GroupMember-only): blocked from itinerary (403 TRIP_ACCESS_FORBIDDEN)
        SharedPreferences.setMockInitialValues({
          'access_token': u3AccessToken,
          'refresh_token': u3RefreshToken,
        });
        await c3.read(groupItineraryProvider.notifier).loadItinerary(groupId);
        final u3Itin = c3.read(groupItineraryProvider);
        expect(u3Itin.isTripAccessForbidden, isTrue);
        expect(u3Itin.lastErrorCode, 'TRIP_ACCESS_FORBIDDEN');
        // ignore: avoid_print
        print('[W10-DEMO] Step 2 PASS: U3 (GroupMember-only) blocked with 403 TRIP_ACCESS_FORBIDDEN');

        // Switch to U2 (Dual permissions): proposes Item 2, votes true -> false -> withdraw
        SharedPreferences.setMockInitialValues({
          'access_token': u2Access,
          'refresh_token': u2Refresh,
        });
        expect(
          await c2.read(groupItineraryProvider.notifier).proposeItem(
                groupId,
                const ProposeGroupItineraryItemRequest(
                  dayNumber: 1,
                  activity: 'Bảo tàng Quảng Ninh',
                  clientRequestId: 'demo-item-2',
                ),
              ),
          isTrue,
        );
        final u2Items = c2.read(groupItineraryProvider).itinerary!.days.first.items;
        expect(u2Items.length, 2);
        final item1 = u2Items[0];
        final item2 = u2Items[1];

        expect(
          await c2
              .read(groupItineraryProvider.notifier)
              .toggleOrSetVote(groupId, item1, true),
          isTrue,
        );
        final afterUp = c2
            .read(groupItineraryProvider)
            .itinerary!
            .days
            .first
            .items
            .first;
        expect(afterUp.score, 1);

        expect(
          await c2
              .read(groupItineraryProvider.notifier)
              .toggleOrSetVote(groupId, afterUp, false),
          isTrue,
        );
        final afterDown = c2
            .read(groupItineraryProvider)
            .itinerary!
            .days
            .first
            .items
            .first;
        expect(afterDown.score, -1);

        expect(
          await c2
              .read(groupItineraryProvider.notifier)
              .toggleOrSetVote(groupId, afterDown, false),
          isTrue,
        );
        final afterWithdraw = c2
            .read(groupItineraryProvider)
            .itinerary!
            .days
            .first
            .items
            .first;
        expect(afterWithdraw.score, 0);
        expect(afterWithdraw.myVote, isNull);
        // ignore: avoid_print
        print('[W10-DEMO] Step 3 PASS: U2 proposed Item 2 and completed vote +1 -> -1 -> withdraw(0)');

        // Switch to U1 (Trip Owner): reorders [item1, item2] -> [item2, item1]
        SharedPreferences.setMockInitialValues({
          'access_token': u1Access,
          'refresh_token': u1Refresh,
        });
        expect(
          await c1.read(groupItineraryProvider.notifier).reorderItems(
                groupId,
                ReorderItineraryRequest(
                  dayNumber: 1,
                  items: [
                    ReorderItineraryItemEntry(itemId: item2.id, orderIndex: 1),
                    ReorderItineraryItemEntry(itemId: item1.id, orderIndex: 2),
                  ],
                ),
              ),
          isTrue,
        );
        expect(
          c1
              .read(groupItineraryProvider)
              .itinerary!
              .days
              .first
              .items
              .map((x) => x.activity)
              .toList(),
          ['Bảo tàng Quảng Ninh', 'Tháp Đồng Hồ Hạ Long'],
        );
        // ignore: avoid_print
        print('[W10-DEMO] Step 4 PASS: Trip Owner U1 reordered itinerary to [Bảo tàng Quảng Ninh, Tháp Đồng Hồ Hạ Long]');

        // Switch to U3 (GroupMember-only CAN use Expenses!): U3 pays 100.000 VND split EQUAL across 3 members
        SharedPreferences.setMockInitialValues({
          'access_token': u3AccessToken,
          'refresh_token': u3RefreshToken,
        });
        expect(
          await c3.read(groupExpenseProvider.notifier).createExpense(
                groupId,
                CreateExpenseRequest(
                  title: 'Ăn trưa hải sản Hạ Long',
                  amount: 100000,
                  paidByUserId: u3Id,
                  splitType: SplitType.equal,
                  participantIds: [u1Id, u2Id, u3Id],
                  clientRequestId: 'demo-exp-100k',
                ),
              ),
          isTrue,
        );
        final expSplits = c3
            .read(groupExpenseProvider)
            .expenseList!
            .expenses
            .first
            .splits
            .map((s) => s.shareAmount)
            .toList();
        expect(expSplits, [33334, 33333, 33333]);
        // ignore: avoid_print
        print('[W10-DEMO] Step 5 PASS: 100.000 VND / 3 split persisted as $expSplits');

        // Admin U1 is a debtor to U3 -> U1 tries to self-confirm own debt -> MUST FAIL (403 SETTLEMENT_FORBIDDEN)!
        SharedPreferences.setMockInitialValues({
          'access_token': u1Access,
          'refresh_token': u1Refresh,
        });
        await c1.read(groupExpenseProvider.notifier).loadLedger(groupId);
        final u1Suggestion = c1
            .read(groupExpenseProvider)
            .settlementPlan!
            .suggestedTransactions
            .firstWhere((s) => s.fromUserId == u1Id.toLowerCase());
        expect(
          await c1.read(groupExpenseProvider.notifier).confirmSettlement(
                groupId,
                CreateSettlementRequest(
                  debtorId: u1Id,
                  creditorId: u3Id,
                  amount: u1Suggestion.amount,
                ),
              ),
          isFalse,
        );
        expect(
          c1.read(groupExpenseProvider).lastErrorCode,
          'SETTLEMENT_FORBIDDEN',
        );

        // Creditor U3 confirms receipt from U1 -> succeeds!
        SharedPreferences.setMockInitialValues({
          'access_token': u3AccessToken,
          'refresh_token': u3RefreshToken,
        });
        expect(
          await c3.read(groupExpenseProvider.notifier).confirmSettlement(
                groupId,
                CreateSettlementRequest(
                  debtorId: u1Id,
                  creditorId: u3Id,
                  amount: u1Suggestion.amount,
                  clientRequestId: 'demo-settle-u1-u3',
                ),
              ),
          isTrue,
        );
        // ignore: avoid_print
        print('[W10-DEMO] Step 6 PASS: Admin debtor self-confirm blocked (403); Creditor U3 confirmed receipt (${u1Suggestion.amount} VND)');

        c1.dispose();
        c2.dispose();
        c3.dispose();
      },
      skip: !live,
    );

    testWidgets(
      'Demo Step 7 (Live Flutter UI Widget): GroupDetailScreen renders real PostgreSQL Chi phí & Đối soát ledger for Creditor U3',
      (tester) async {
        SharedPreferences.setMockInitialValues({
          'access_token': u3AccessToken,
          'refresh_token': u3RefreshToken,
        });

        late GroupModel liveGroup;
        late ExpenseListModel liveExpenses;
        late SettlementPlanModel livePlan;
        late UserProfile liveProfile;

        await tester.runAsync(() async {
          final fetchContainer = _buildLiveContainer(baseUrl);
          try {
            await fetchContainer
                .read(groupDetailProvider.notifier)
                .loadGroup(groupId);
            await fetchContainer
                .read(groupExpenseProvider.notifier)
                .loadLedger(groupId);
            final meRes = await fetchContainer
                .read(apiClientProvider)
                .get('/users/me');
            liveProfile = UserProfile.fromJson(
              Map<String, dynamic>.from(meRes.data['data'] as Map),
            );
            liveGroup = fetchContainer.read(groupDetailProvider).group!;
            liveExpenses = fetchContainer.read(groupExpenseProvider).expenseList!;
            livePlan = fetchContainer.read(groupExpenseProvider).settlementPlan!;
          } finally {
            fetchContainer.dispose();
          }
        });

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              groupRepositoryProvider.overrideWith(
                (ref) => _LiveFetchedW10GroupRepo(
                  ref.read(apiClientProvider),
                  preloadedGroup: liveGroup,
                  preloadedExpenses: liveExpenses,
                  preloadedPlan: livePlan,
                ),
              ),
              profileRepositoryProvider.overrideWith(
                (ref) => _LiveFetchedProfileRepo(
                  ref.read(apiClientProvider),
                  liveProfile,
                ),
              ),
            ],
            child: MaterialApp(home: GroupDetailScreen(groupId: groupId)),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.text('Nhóm Demo Hạ Long W10'), findsWidgets);
        await tester.tap(find.text('Chi phí'));
        await tester.pumpAndSettle();

        expect(find.text('100.000 đ'), findsWidgets);
        expect(find.byKey(const Key('group_expense_locked_banner')), findsOneWidget);
      },
      skip: !live,
    );
  });
}
