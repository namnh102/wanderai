import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/features/auth/data/auth_repository.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/groups/data/group_expense_models.dart';
import 'package:wanderai_mobile/features/groups/data/group_itinerary_models.dart';
import 'package:wanderai_mobile/features/groups/data/group_models.dart';
import 'package:wanderai_mobile/features/groups/data/group_repository.dart';
import 'package:wanderai_mobile/features/groups/presentation/group_detail_screen.dart';
import 'package:wanderai_mobile/features/groups/providers/group_expense_provider.dart';
import 'package:wanderai_mobile/features/groups/providers/group_itinerary_provider.dart';
import 'package:wanderai_mobile/features/profile/data/profile_models.dart';
import 'package:wanderai_mobile/features/profile/data/profile_repository.dart';
import 'package:wanderai_mobile/features/trips/data/trip_models.dart';

class _StubProfileRepo extends ProfileRepository {
  final UserProfile user;
  _StubProfileRepo(this.user) : super(Dio());

  @override
  Future<UserProfile> getProfile() async => user;
}

class _StubAuthRepo extends AuthRepository {
  bool loggedIn = true;
  _StubAuthRepo() : super(Dio());

  @override
  Future<bool> restoreSession() async => loggedIn;

  @override
  Future<void> logout() async {
    loggedIn = false;
  }
}

class _FakeW10GroupRepository extends GroupRepository {
  GroupModel group;
  GroupItineraryStateModel? itinerary;
  DioException? itineraryError;
  ExpenseListModel expenseList;
  SettlementPlanModel settlementPlan;
  int voteCalls = 0;
  int withdrawCalls = 0;
  int settlementCalls = 0;

  _FakeW10GroupRepository({
    required this.group,
    this.itinerary,
    required this.expenseList,
    required this.settlementPlan,
  }) : super(Dio());

  @override
  Future<GroupModel> getGroup(String id) async => group;

  @override
  Future<GroupItineraryStateModel> getGroupItinerary(String groupId) async {
    if (itineraryError != null) throw itineraryError!;
    return itinerary!;
  }

  @override
  Future<GroupItineraryItemModel> proposeItineraryItem(
    String groupId,
    ProposeGroupItineraryItemRequest request,
  ) async {
    final created = GroupItineraryItemModel(
      id: 'item-new-1',
      itineraryId: 'day-1',
      dayNumber: request.dayNumber,
      orderIndex: 2,
      activity: request.activity,
      canDelete: true,
    );
    final oldDays = itinerary!.days;
    itinerary = itinerary!.copyWith(
      days: [
        GroupItineraryDayModel(
          itineraryId: 'day-1',
          dayNumber: 1,
          items: [
            ...(oldDays.isNotEmpty ? oldDays.first.items : const []),
            created,
          ],
        ),
      ],
    );
    return created;
  }

  @override
  Future<GroupVoteResultModel> voteItineraryItem(
    String groupId,
    String itemId, {
    required bool vote,
  }) async {
    voteCalls++;
    return GroupVoteResultModel(
      itemId: itemId,
      upvotes: vote ? 1 : 0,
      downvotes: vote ? 0 : 1,
      score: vote ? 1 : -1,
      myVote: vote,
    );
  }

  @override
  Future<GroupVoteResultModel> withdrawItineraryVote(
    String groupId,
    String itemId,
  ) async {
    withdrawCalls++;
    return GroupVoteResultModel(
      itemId: itemId,
      upvotes: 0,
      downvotes: 0,
      score: 0,
      myVote: null,
    );
  }

  @override
  Future<GroupItineraryStateModel> reorderGroupItinerary(
    String groupId,
    ReorderItineraryRequest request,
  ) async {
    return itinerary!;
  }

  @override
  Future<ExpenseListModel> listExpenses(String groupId) async => expenseList;

  @override
  Future<SettlementPlanModel> getSettlementPlan(String groupId) async =>
      settlementPlan;

  @override
  Future<SettlementModel> createSettlement(
    String groupId,
    CreateSettlementRequest request,
  ) async {
    settlementCalls++;
    final st = SettlementModel(
      id: 'st-1',
      groupId: groupId,
      debtorId: request.debtorId,
      debtor: const GroupMemberUserModel(id: 'u1', displayName: 'Admin U1'),
      creditorId: request.creditorId,
      creditor: const GroupMemberUserModel(id: 'u3', displayName: 'Member U3'),
      createdByUserId: 'u3',
      amount: request.amount,
      settledAt: DateTime(2026, 11, 26),
    );
    settlementPlan = SettlementPlanModel(
      groupId: groupId,
      totalSpent: settlementPlan.totalSpent,
      totalOutstandingDebt: 0,
      balances: const [],
      suggestedTransactions: const [],
      settlements: [st],
    );
    expenseList = ExpenseListModel(
      groupId: groupId,
      hasSettlements: true,
      totalSpent: expenseList.totalSpent,
      expenseCount: expenseList.expenseCount,
      expenses: expenseList.expenses,
    );
    return st;
  }
}

GroupModel _sampleGroup({GroupRole? myRole}) {
  return GroupModel(
    id: 'g-w10',
    name: 'Nhóm Hạ Long W10',
    tripId: 't-w10',
    tripTitle: 'Chuyến Hạ Long',
    tripOwnerId: 'u1',
    myRole: myRole,
    memberCount: 3,
    members: const [
      GroupMemberModel(
        id: 'm1',
        groupId: 'g-w10',
        userId: 'u1',
        role: GroupRole.admin,
        rawRole: 'admin',
        isTripOwner: true,
        user: GroupMemberUserModel(id: 'u1', displayName: 'Chủ Chuyến U1'),
      ),
      GroupMemberModel(
        id: 'm2',
        groupId: 'g-w10',
        userId: 'u2',
        role: GroupRole.member,
        rawRole: 'member',
        user: GroupMemberUserModel(id: 'u2', displayName: 'Thành Viên U2'),
      ),
      GroupMemberModel(
        id: 'm3',
        groupId: 'g-w10',
        userId: 'u3',
        role: GroupRole.member,
        rawRole: 'member',
        user: GroupMemberUserModel(id: 'u3', displayName: 'Chỉ Nhóm U3'),
      ),
    ],
  );
}

void main() {
  test('previewEqualSplits distributes 100.000 VND / 3 as 33.334 + 33.333 + 33.333 across reversed input orders', () {
    for (final perm in [
      ['u1', 'u2', 'u3'],
      ['u3', 'u2', 'u1'],
      ['U2', 'u3', 'U1'],
    ]) {
      final splits = previewEqualSplits(100000, perm);
      expect(splits, [
        (userId: 'u1', shareAmount: 33334),
        (userId: 'u2', shareAmount: 33333),
        (userId: 'u3', shareAmount: 33333),
      ]);
      expect(splits.fold<int>(0, (sum, e) => sum + e.shareAmount), 100000);
    }
  });

  testWidgets(
    'W10 UI: vote switch/withdraw works; GroupMember-only sees 403 Trip gate; Admin debtor CANNOT self-confirm settlement while Creditor CAN confirm',
    (tester) async {
      final repo = _FakeW10GroupRepository(
        group: _sampleGroup(),
        itinerary: const GroupItineraryStateModel(
          groupId: 'g-w10',
          tripLinked: true,
          tripId: 't-w10',
          tripTitle: 'Chuyến Hạ Long',
          tripStatus: 'PLANNED',
          canReorder: true,
          days: [
            GroupItineraryDayModel(
              itineraryId: 'day-1',
              dayNumber: 1,
              items: [
                GroupItineraryItemModel(
                  id: 'item-1',
                  itineraryId: 'day-1',
                  dayNumber: 1,
                  orderIndex: 1,
                  activity: 'Tháp Đồng Hồ',
                  canDelete: true,
                ),
              ],
            ),
          ],
        ),
        expenseList: ExpenseListModel(
          groupId: 'g-w10',
          totalSpent: 100000,
          expenseCount: 1,
          expenses: [
            ExpenseModel(
              id: 'exp-1',
              groupId: 'g-w10',
              title: 'Taxi nhóm',
              amount: 100000,
              category: ExpenseCategory.transport,
              splitType: SplitType.equal,
              expenseDate: DateTime(2026, 11, 26),
              paidByUserId: 'u3',
              createdByUserId: 'u3',
              createdAt: DateTime(2026, 11, 26),
              canDelete: true,
            ),
          ],
        ),
        settlementPlan: const SettlementPlanModel(
          groupId: 'g-w10',
          totalSpent: 100000,
          totalOutstandingDebt: 33334,
          suggestedTransactions: [
            // Admin u1 owes Member u3 33.334 VND!
            SuggestedSettlementModel(
              fromUserId: 'u1',
              fromUser: GroupMemberUserModel(
                id: 'u1',
                displayName: 'Chủ Chuyến U1',
              ),
              toUserId: 'u3',
              toUser: GroupMemberUserModel(
                id: 'u3',
                displayName: 'Chỉ Nhóm U3',
              ),
              amount: 33334,
            ),
          ],
        ),
      );

      // 1. Mount as Admin U1 (who is the DEBTOR in u1 -> u3!)
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            groupRepositoryProvider.overrideWithValue(repo),
            profileRepositoryProvider.overrideWithValue(
              _StubProfileRepo(const UserProfile(id: 'u1', email: 'u1@t')),
            ),
          ],
          child: const MaterialApp(home: GroupDetailScreen(groupId: 'g-w10')),
        ),
      );
      await tester.pumpAndSettle();

      // Switch to Lịch trình tab -> upvote -> switch to downvote -> withdraw
      await tester.tap(find.text('Lịch trình'));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('group_itinerary_upvote_item-1')));
      await tester.pumpAndSettle();
      expect(find.text('Điểm: +1'), findsOneWidget);

      await tester.tap(find.byKey(const Key('group_itinerary_downvote_item-1')));
      await tester.pumpAndSettle();
      expect(find.text('Điểm: -1'), findsOneWidget);

      await tester.tap(find.byKey(const Key('group_itinerary_downvote_item-1')));
      await tester.pumpAndSettle();
      expect(find.text('Điểm: +0'), findsOneWidget);
      expect(repo.voteCalls, 2);
      expect(repo.withdrawCalls, 1);

      // Switch to Chi phí tab as Admin U1 (debtor) -> Confirm button MUST NOT exist!
      await tester.tap(find.text('Chi phí'));
      await tester.pumpAndSettle();
      expect(find.text('Gợi ý giảm lượt chuyển trả'), findsOneWidget);
      expect(
        find.byKey(const Key('group_confirm_settlement_u1_u3')),
        findsNothing,
      );
      expect(
        find.byKey(const Key('group_awaiting_creditor_badge_u1_u3')),
        findsOneWidget,
      );

      // 2. Remount as U3 (GroupMember-only, Creditor!)
      repo.itinerary = null;
      repo.itineraryError = DioException(
        requestOptions: RequestOptions(path: '/groups/g-w10/itinerary'),
        response: Response(
          requestOptions: RequestOptions(path: '/groups/g-w10/itinerary'),
          statusCode: 403,
          data: {
            'errorCode': 'TRIP_ACCESS_FORBIDDEN',
            'message': 'Chưa được cấp quyền chuyến đi',
          },
        ),
        type: DioExceptionType.badResponse,
      );

      await tester.pumpWidget(
        ProviderScope(
          key: const ValueKey('u3-scope'),
          overrides: [
            groupRepositoryProvider.overrideWithValue(repo),
            profileRepositoryProvider.overrideWithValue(
              _StubProfileRepo(const UserProfile(id: 'u3', email: 'u3@t')),
            ),
          ],
          child: const MaterialApp(
            key: ValueKey('u3-session'),
            home: GroupDetailScreen(groupId: 'g-w10'),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // U3 opens Lịch trình -> sees clear 403 Trip Gate state
      await tester.tap(find.text('Lịch trình'));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('group_itinerary_trip_forbidden_state')),
        findsOneWidget,
      );

      // U3 opens Chi phí -> CAN view ledger AND confirm u1 -> u3 receipt!
      await tester.tap(find.text('Chi phí'));
      await tester.pumpAndSettle();
      final confirmBtn = find.byKey(const Key('group_confirm_settlement_u1_u3'));
      expect(confirmBtn, findsOneWidget);
      await tester.ensureVisible(confirmBtn);
      await tester.pumpAndSettle();
      await tester.tap(confirmBtn);
      await tester.pumpAndSettle();

      expect(repo.settlementCalls, 1);
      expect(find.byKey(const Key('group_expense_locked_banner')), findsOneWidget);
    },
  );

  test('TC-DEMO-02: resetSessionScopedState clears both groupItineraryProvider and groupExpenseProvider on logout', () async {
    final repo = _FakeW10GroupRepository(
      group: _sampleGroup(),
      itinerary: const GroupItineraryStateModel(
        groupId: 'g-w10',
        tripLinked: true,
        tripId: 't-w10',
      ),
      expenseList: const ExpenseListModel(groupId: 'g-w10', totalSpent: 100000),
      settlementPlan: const SettlementPlanModel(groupId: 'g-w10'),
    );
    final authRepo = _StubAuthRepo();

    final container = ProviderContainer(
      overrides: [
        authRepositoryProvider.overrideWithValue(authRepo),
        groupRepositoryProvider.overrideWithValue(repo),
      ],
    );
    addTearDown(container.dispose);

    container.read(routerNotifierProvider);
    await Future<void>.delayed(const Duration(milliseconds: 20));
    await container.read(groupItineraryProvider.notifier).loadItinerary('g-w10');
    await container.read(groupExpenseProvider.notifier).loadLedger('g-w10');
    expect(container.read(groupItineraryProvider).itinerary, isNotNull);
    expect(container.read(groupExpenseProvider).expenseList, isNotNull);

    await container.read(authProvider.notifier).logout();
    await Future<void>.delayed(const Duration(milliseconds: 20));

    expect(container.read(groupItineraryProvider).itinerary, isNull);
    expect(container.read(groupExpenseProvider).expenseList, isNull);
  });

  testWidgets(
    'W10 UI RBAC buttons: reorder/delete item visibility & soft-deleted creditor with sole-admin debtor hides confirm until another admin exists',
    (tester) async {
      final repo = _FakeW10GroupRepository(
        group: _sampleGroup(),
        itinerary: const GroupItineraryStateModel(
          groupId: 'g-w10',
          tripLinked: true,
          tripId: 't-w10',
          tripTitle: 'Chuyến Hạ Long',
          tripStatus: 'PLANNED',
          canReorder: false,
          days: [
            GroupItineraryDayModel(
              itineraryId: 'day-1',
              dayNumber: 1,
              items: [
                GroupItineraryItemModel(
                  id: 'item-owner',
                  itineraryId: 'day-1',
                  dayNumber: 1,
                  orderIndex: 1,
                  activity: 'Mục của U1',
                  canDelete: false,
                ),
                GroupItineraryItemModel(
                  id: 'item-u2',
                  itineraryId: 'day-1',
                  dayNumber: 1,
                  orderIndex: 2,
                  activity: 'Mục của U2',
                  canDelete: true,
                ),
              ],
            ),
          ],
        ),
        expenseList: const ExpenseListModel(groupId: 'g-w10', totalSpent: 40000),
        settlementPlan: const SettlementPlanModel(
          groupId: 'g-w10',
          totalSpent: 40000,
          totalOutstandingDebt: 40000,
          suggestedTransactions: [
            SuggestedSettlementModel(
              fromUserId: 'u1',
              fromUser: GroupMemberUserModel(
                id: 'u1',
                displayName: 'Chủ Chuyến U1',
              ),
              toUserId: 'u-deleted',
              toUser: GroupMemberUserModel(
                id: 'u-deleted',
                displayName: 'Tài khoản đã xóa',
              ),
              amount: 40000,
            ),
          ],
        ),
      );

      // 1. Mount as U2 (member with TripMember): canReorder=false hides reorder button; only own item has delete button;
      // on Chi phí tab, neither sole-admin debtor U1 nor regular member U2 sees confirm button for soft-deleted creditor!
      await tester.pumpWidget(
        ProviderScope(
          key: const ValueKey('rbac-u2-member'),
          overrides: [
            groupRepositoryProvider.overrideWithValue(repo),
            profileRepositoryProvider.overrideWithValue(
              _StubProfileRepo(const UserProfile(id: 'u2', email: 'u2@t')),
            ),
          ],
          child: const MaterialApp(home: GroupDetailScreen(groupId: 'g-w10')),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Lịch trình'));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('group_itinerary_reorder_toggle')), findsNothing);
      expect(find.byKey(const Key('group_itinerary_delete_item-owner')), findsNothing);
      expect(find.byKey(const Key('group_itinerary_delete_item-u2')), findsOneWidget);

      await tester.tap(find.text('Chi phí'));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('group_confirm_settlement_u1_u-deleted')),
        findsNothing,
      );

      // 2. Mount as U1 (sole admin & debtor): STILL no confirm button!
      await tester.pumpWidget(
        ProviderScope(
          key: const ValueKey('rbac-u1-sole-admin-debtor'),
          overrides: [
            groupRepositoryProvider.overrideWithValue(repo),
            profileRepositoryProvider.overrideWithValue(
              _StubProfileRepo(const UserProfile(id: 'u1', email: 'u1@t')),
            ),
          ],
          child: const MaterialApp(home: GroupDetailScreen(groupId: 'g-w10')),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Chi phí'));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('group_confirm_settlement_u1_u-deleted')),
        findsNothing,
      );

      // 3. Promote U2 to valid Group admin (U2 != debtor U1): now U2 DOES see confirm button!
      repo.group = GroupModel(
        id: 'g-w10',
        name: 'Nhóm Hạ Long W10',
        tripId: 't-w10',
        tripTitle: 'Chuyến Hạ Long',
        tripOwnerId: 'u1',
        myRole: GroupRole.admin,
        memberCount: 3,
        members: [
          repo.group.members[0],
          const GroupMemberModel(
            id: 'm2',
            groupId: 'g-w10',
            userId: 'u2',
            role: GroupRole.admin,
            rawRole: 'admin',
            user: GroupMemberUserModel(id: 'u2', displayName: 'Admin Thứ Hai U2'),
          ),
          repo.group.members[2],
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          key: const ValueKey('rbac-u2-second-admin'),
          overrides: [
            groupRepositoryProvider.overrideWithValue(repo),
            profileRepositoryProvider.overrideWithValue(
              _StubProfileRepo(const UserProfile(id: 'u2', email: 'u2@t')),
            ),
          ],
          child: const MaterialApp(home: GroupDetailScreen(groupId: 'g-w10')),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Chi phí'));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const Key('group_confirm_settlement_u1_u-deleted')),
        findsOneWidget,
      );
    },
  );
}
