import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/core/widgets/app_loading.dart';
import 'package:wanderai_mobile/features/auth/data/auth_models.dart';
import 'package:wanderai_mobile/features/auth/data/auth_repository.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/groups/data/group_models.dart';
import 'package:wanderai_mobile/features/groups/data/group_repository.dart';
import 'package:wanderai_mobile/features/groups/presentation/group_detail_screen.dart';
import 'package:wanderai_mobile/features/groups/presentation/group_list_screen.dart';
import 'package:wanderai_mobile/features/groups/providers/group_provider.dart';
import 'package:wanderai_mobile/features/profile/data/profile_models.dart';
import 'package:wanderai_mobile/features/profile/data/profile_repository.dart';
import 'package:wanderai_mobile/features/trips/data/trip_models.dart';
import 'package:wanderai_mobile/features/trips/data/trip_repository.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_detail_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_list_screen.dart';
import 'package:wanderai_mobile/features/trips/providers/trip_provider.dart';

class FakeGroupRepository extends GroupRepository {
  List<GroupModel> groups = [];
  GroupModel? detailGroup;
  DioException? listError;
  DioException? detailError;
  DioException? mutationError;
  int updateCalls = 0;
  String? lastUpdatedName;
  String? lastAddedUserId;

  FakeGroupRepository() : super(Dio());

  @override
  Future<List<GroupModel>> listGroups() async {
    if (listError != null) throw listError!;
    return groups;
  }

  @override
  Future<GroupModel> getGroup(String id) async {
    if (detailError != null) throw detailError!;
    if (detailGroup != null) return detailGroup!;
    return groups.firstWhere((g) => g.id == id);
  }

  @override
  Future<GroupModel> createGroup(CreateGroupRequest request) async {
    if (mutationError != null) throw mutationError!;
    final created = GroupModel(
      id: 'group-created-1',
      name: request.name.trim(),
      description: request.description?.trim(),
      tripId: request.tripId,
      myRole: GroupRole.admin,
      memberCount: 1,
      members: const [],
    );
    groups = [created, ...groups];
    detailGroup = created;
    return created;
  }

  @override
  Future<GroupModel> updateGroup(String id, UpdateGroupRequest request) async {
    if (mutationError != null) throw mutationError!;
    updateCalls++;
    lastUpdatedName = request.name;
    final current = detailGroup!;
    final updated = GroupModel(
      id: current.id,
      name: request.name ?? current.name,
      description: request.description ?? current.description,
      tripId: current.tripId,
      tripTitle: current.tripTitle,
      tripOwnerId: current.tripOwnerId,
      myRole: current.myRole,
      memberCount: current.memberCount,
      members: current.members,
    );
    detailGroup = updated;
    return updated;
  }

  @override
  Future<void> addMember(String groupId, AddGroupMemberRequest request) async {
    if (mutationError != null) throw mutationError!;
    lastAddedUserId = request.userId;
  }

  @override
  Future<void> removeMember(String groupId, String userId) async {
    if (mutationError != null) throw mutationError!;
    final current = detailGroup!;
    final nextMembers =
        current.members.where((m) => m.userId != userId).toList();
    detailGroup = GroupModel(
      id: current.id,
      name: current.name,
      description: current.description,
      tripId: current.tripId,
      myRole: current.myRole,
      memberCount: nextMembers.length,
      members: nextMembers,
    );
  }
}

class _DeferredGroupRepository extends GroupRepository {
  final Completer<List<GroupModel>> listCompleter = Completer();
  final Completer<GroupModel> detailCompleter = Completer();
  DioException? createError;
  GroupModel? createResult;

  _DeferredGroupRepository() : super(Dio());

  @override
  Future<List<GroupModel>> listGroups() => listCompleter.future;

  @override
  Future<GroupModel> getGroup(String id) => detailCompleter.future;

  @override
  Future<GroupModel> createGroup(CreateGroupRequest request) async {
    if (createError != null) throw createError!;
    return createResult ??
        GroupModel(
          id: 'group-concurrent-1',
          name: request.name.trim(),
          description: request.description?.trim(),
          tripId: request.tripId,
          myRole: GroupRole.admin,
          memberCount: 1,
          members: const [],
        );
  }
}

class _StubProfileRepo extends ProfileRepository {
  final UserProfile user;
  _StubProfileRepo(this.user) : super(Dio());

  @override
  Future<UserProfile> getProfile() async => user;
}

class _StubAuthRepo extends AuthRepository {
  String? userId;
  _StubAuthRepo(this.userId) : super(Dio());

  @override
  Future<bool> restoreSession() async => userId != null;

  @override
  Future<AuthTokens> login(LoginRequest request) async {
    userId = 'user-b';
    return const AuthTokens(accessToken: 'a', refreshToken: 'r');
  }

  @override
  Future<void> logout() async {
    userId = null;
  }
}

class _StubTripRepo extends TripRepository {
  _StubTripRepo() : super(Dio());

  @override
  Future<List<TripModel>> getMyTrips() async => const [];

  @override
  Future<TripModel> getTripDetail(String id) async => TripModel(
        id: id,
        userId: 'admin-1',
        title: 'Chuyến đi Hạ Long',
      );
}

DioException _httpError(int statusCode, String message) {
  return DioException(
    requestOptions: RequestOptions(path: '/groups'),
    type: DioExceptionType.badResponse,
    response: Response(
      requestOptions: RequestOptions(path: '/groups'),
      statusCode: statusCode,
      data: {'message': message},
    ),
  );
}

GroupModel _sampleGroup({
  GroupRole myRole = GroupRole.admin,
  bool includeMembers = true,
}) {
  const adminMember = GroupMemberModel(
    id: 'gm-1',
    groupId: 'g-1',
    userId: 'admin-1',
    role: GroupRole.admin,
    rawRole: 'admin',
    isTripOwner: true,
    user: GroupMemberUserModel(
      id: 'admin-1',
      displayName: 'Trưởng Nhóm An',
      bio: 'Thích khám phá Hạ Long',
    ),
  );
  const regularMember = GroupMemberModel(
    id: 'gm-2',
    groupId: 'g-1',
    userId: 'member-1',
    role: GroupRole.member,
    rawRole: 'member',
    isTripOwner: false,
    user: GroupMemberUserModel(
      id: 'member-1',
      displayName: 'Thành Viên Bình',
      bio: 'Nhiếp ảnh du lịch',
    ),
  );

  final members = includeMembers ? [adminMember, regularMember] : const <GroupMemberModel>[];
  return GroupModel(
    id: 'g-1',
    name: 'Nhóm Hạ Long 2N1Đ',
    description: 'Cùng đi Tháp Đồng Hồ và Bảo tàng Quảng Ninh',
    tripId: 'trip-1',
    tripTitle: 'Hạ Long cuối tuần',
    tripOwnerId: 'admin-1',
    myRole: myRole,
    memberCount: members.length,
    members: members,
  );
}

void main() {
  group('Group models & PII safety', () {
    test('AddGroupMemberRequest.toJson sends only userId', () {
      const req = AddGroupMemberRequest(
        userId: ' 11111111-1111-4111-8111-111111111111 ',
      );
      expect(req.toJson(), {'userId': '11111111-1111-4111-8111-111111111111'});
    });

    test('GroupModel.fromJson parses myRole, memberCount, and never retains PII', () {
      final parsed = GroupModel.fromJson({
        'id': 'g-1',
        'name': 'Nhóm Hạ Long',
        'myRole': 'admin',
        'memberCount': 1,
        'members': [
          {
            'id': 'gm-1',
            'groupId': 'g-1',
            'userId': 'u-1',
            'role': 'admin',
            'user': {
              'id': 'u-1',
              'displayName': 'An Nguyễn',
              'email': 'secret@example.com',
              'phone': '+84901234567',
              'bio': 'Du lịch biển',
            },
          },
        ],
      });

      expect(parsed.myRole, GroupRole.admin);
      expect(parsed.memberCount, 1);
      expect(parsed.members.single.user.displayName, 'An Nguyễn');
      expect(parsed.members.single.user.bio, 'Du lịch biển');
    });
  });

  group('Group providers & session isolation', () {
    test('GroupDetailNotifier handles 403, 404, 409 action error, and safe dispose', () async {
      final repo = FakeGroupRepository()
        ..detailError = _httpError(403, 'Bạn không phải thành viên của nhóm này');

      final container = ProviderContainer(
        overrides: [groupRepositoryProvider.overrideWithValue(repo)],
      );
      await container.read(groupDetailProvider.notifier).loadGroup('g-1');
      expect(container.read(groupDetailProvider).isForbidden, isTrue);
      expect(container.read(groupDetailProvider).group, isNull);

      repo.detailError = _httpError(404, 'Nhóm đồng hành không tồn tại');
      await container.read(groupDetailProvider.notifier).loadGroup('g-404');
      expect(container.read(groupDetailProvider).isNotFound, isTrue);

      repo.detailError = null;
      repo.detailGroup = _sampleGroup();
      await container.read(groupDetailProvider.notifier).loadGroup('g-1');
      repo.mutationError = _httpError(409, 'Người dùng đã là thành viên của nhóm');
      final added = await container
          .read(groupDetailProvider.notifier)
          .addMember('g-1', 'member-1');
      expect(added, isFalse);
      expect(
        container.read(groupDetailProvider).actionErrorMessage,
        contains('đã là thành viên'),
      );
      container.dispose();
    });

    test('resetSessionScopedState clears groupListProvider and groupDetailProvider on logout', () async {
      final authRepo = _StubAuthRepo('user-a');
      final groupRepo = FakeGroupRepository()
        ..groups = [_sampleGroup()]
        ..detailGroup = _sampleGroup();

      final container = ProviderContainer(
        overrides: [
          authRepositoryProvider.overrideWithValue(authRepo),
          groupRepositoryProvider.overrideWithValue(groupRepo),
        ],
      );
      addTearDown(container.dispose);

      container.read(routerNotifierProvider);
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await container.read(groupListProvider.notifier).loadGroups();
      await container.read(groupDetailProvider.notifier).loadGroup('g-1');
      expect(container.read(groupListProvider).groups, hasLength(1));
      expect(container.read(groupDetailProvider).group, isNotNull);

      await container.read(authProvider.notifier).logout();
      await Future<void>.delayed(const Duration(milliseconds: 20));

      expect(container.read(groupListProvider).groups, isEmpty);
      expect(container.read(groupDetailProvider).group, isNull);
    });

    test('GroupListNotifier does not cancel in-flight loadGroups or stick isLoading=true when createGroup fails', () async {
      final repo = _DeferredGroupRepository()
        ..createError = _httpError(409, 'Chuyến đi này đã có nhóm đồng hành');

      final container = ProviderContainer(
        overrides: [groupRepositoryProvider.overrideWithValue(repo)],
      );
      addTearDown(container.dispose);

      final loadFuture = container.read(groupListProvider.notifier).loadGroups();
      expect(container.read(groupListProvider).isLoading, isTrue);

      final created = await container
          .read(groupListProvider.notifier)
          .createGroup(const CreateGroupRequest(name: 'Nhóm lỗi'));
      expect(created, isNull);
      expect(container.read(groupListProvider).isCreating, isFalse);
      expect(
        container.read(groupListProvider).actionErrorMessage,
        contains('đã có nhóm đồng hành'),
      );

      // In-flight loadGroups must still complete and clear isLoading -> false
      repo.listCompleter.complete(const []);
      await loadFuture;
      expect(container.read(groupListProvider).isLoading, isFalse);
      expect(container.read(groupListProvider).isEmpty, isTrue);

      container.read(groupListProvider.notifier).clearActionError();
      expect(container.read(groupListProvider).actionErrorMessage, isNull);
    });

    test('GroupListNotifier preserves newly created group when in-flight loadGroups resolves afterwards', () async {
      final repo = _DeferredGroupRepository();
      final container = ProviderContainer(
        overrides: [groupRepositoryProvider.overrideWithValue(repo)],
      );
      addTearDown(container.dispose);

      final loadFuture = container.read(groupListProvider.notifier).loadGroups();
      final created = await container
          .read(groupListProvider.notifier)
          .createGroup(const CreateGroupRequest(name: 'Nhóm mới song song'));
      expect(created, isNotNull);

      repo.listCompleter.complete([_sampleGroup()]);
      await loadFuture;

      expect(container.read(groupListProvider).isLoading, isFalse);
      expect(
        container.read(groupListProvider).groups.map((g) => g.id),
        containsAll(['group-concurrent-1', 'g-1']),
      );
    });
  });

  group('Group widget UI states & navigation', () {
    testWidgets('shows AppLoading while GroupListScreen and GroupDetailScreen are loading', (tester) async {
      final deferred = _DeferredGroupRepository();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            groupRepositoryProvider.overrideWithValue(deferred),
            profileRepositoryProvider.overrideWithValue(
              _StubProfileRepo(const UserProfile(id: 'admin-1', email: 'a@t')),
            ),
          ],
          child: const MaterialApp(home: GroupListScreen()),
        ),
      );
      await tester.pump();
      expect(find.byType(AppLoading), findsOneWidget);
      deferred.listCompleter.complete(const []);
      await tester.pumpAndSettle();
      expect(find.text('Chưa có nhóm chuyến đi nào'), findsOneWidget);

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            groupRepositoryProvider.overrideWithValue(deferred),
            profileRepositoryProvider.overrideWithValue(
              _StubProfileRepo(const UserProfile(id: 'admin-1', email: 'a@t')),
            ),
          ],
          child: const MaterialApp(home: GroupDetailScreen(groupId: 'g-1')),
        ),
      );
      await tester.pump();
      expect(find.byType(AppLoading), findsOneWidget);
      deferred.detailCompleter.complete(_sampleGroup(includeMembers: false));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('group_members_empty_state')), findsOneWidget);
    });

    testWidgets('shows 403 Access Denied state when outsider opens GroupDetailScreen', (tester) async {
      final repo = FakeGroupRepository()
        ..detailError = _httpError(403, 'Bạn không phải thành viên của nhóm này');

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            groupRepositoryProvider.overrideWithValue(repo),
            profileRepositoryProvider.overrideWithValue(
              _StubProfileRepo(const UserProfile(id: 'outsider-1', email: 'o@t')),
            ),
          ],
          child: const MaterialApp(home: GroupDetailScreen(groupId: 'g-1')),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('group_detail_forbidden_state')), findsOneWidget);
      expect(find.text('Truy cập bị từ chối (403)'), findsOneWidget);
    });

    testWidgets('admin sees role badges, zero PII emails, and can edit group title', (tester) async {
      final repo = FakeGroupRepository()
        ..detailGroup = _sampleGroup(myRole: GroupRole.admin);

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            groupRepositoryProvider.overrideWithValue(repo),
            profileRepositoryProvider.overrideWithValue(
              _StubProfileRepo(const UserProfile(id: 'admin-1', email: 'admin@hidden.vn')),
            ),
          ],
          child: const MaterialApp(home: GroupDetailScreen(groupId: 'g-1')),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Trưởng Nhóm An (Bạn)'), findsOneWidget);
      expect(find.text('Thành Viên Bình'), findsOneWidget);
      expect(find.text('Trưởng nhóm (admin)'), findsWidgets);
      expect(find.text('Thành viên (member)'), findsOneWidget);
      expect(find.textContaining('@'), findsNothing);

      expect(find.byKey(const Key('group_edit_button')), findsOneWidget);
      expect(find.byKey(const Key('group_add_member_button')), findsOneWidget);
      expect(find.byKey(const Key('group_remove_member_btn_member-1')), findsOneWidget);

      await tester.tap(find.byKey(const Key('group_edit_button')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('group_edit_name_input')),
        'Nhóm Hạ Long Mới',
      );
      await tester.tap(find.byKey(const Key('group_edit_submit_button')));
      await tester.pumpAndSettle();

      expect(repo.updateCalls, 1);
      expect(repo.lastUpdatedName, 'Nhóm Hạ Long Mới');
      expect(find.text('Nhóm Hạ Long Mới'), findsWidgets);
    });

    testWidgets('_CreateGroupDialog clears actionErrorMessage on cancel and reopen', (tester) async {
      final repo = FakeGroupRepository()
        ..mutationError = _httpError(409, 'Chuyến đi này đã có nhóm đồng hành');

      final container = ProviderContainer(
        overrides: [
          groupRepositoryProvider.overrideWithValue(repo),
          profileRepositoryProvider.overrideWithValue(
            _StubProfileRepo(const UserProfile(id: 'admin-1', email: 'a@t')),
          ),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: GroupListScreen()),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('group_list_create_button')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('group_create_name_input')),
        'Nhóm trùng trip',
      );
      await tester.tap(find.byKey(const Key('group_create_submit_button')));
      await tester.pumpAndSettle();

      expect(find.text('Chuyến đi này đã có nhóm đồng hành'), findsWidgets);
      expect(
        container.read(groupListProvider).actionErrorMessage,
        'Chuyến đi này đã có nhóm đồng hành',
      );

      await tester.tap(find.byKey(const Key('group_create_cancel_button')));
      await tester.pumpAndSettle();

      expect(container.read(groupListProvider).actionErrorMessage, isNull);
      expect(find.text('Chuyến đi này đã có nhóm đồng hành'), findsNothing);

      // Reopen dialog: stale error remains cleared
      await tester.tap(find.byKey(const Key('group_list_create_button')));
      await tester.pumpAndSettle();
      expect(find.text('Chuyến đi này đã có nhóm đồng hành'), findsNothing);
    });

    testWidgets('_EditGroupDialog rejects names exceeding 120 characters', (tester) async {
      final repo = FakeGroupRepository()
        ..detailGroup = _sampleGroup(myRole: GroupRole.admin);

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            groupRepositoryProvider.overrideWithValue(repo),
            profileRepositoryProvider.overrideWithValue(
              _StubProfileRepo(const UserProfile(id: 'admin-1', email: 'a@t')),
            ),
          ],
          child: const MaterialApp(home: GroupDetailScreen(groupId: 'g-1')),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('group_edit_button')));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('group_edit_name_input')),
        'A' * 121,
      );
      await tester.tap(find.byKey(const Key('group_edit_submit_button')));
      await tester.pumpAndSettle();

      expect(find.text('Tên nhóm tối đa 120 ký tự'), findsOneWidget);
      expect(repo.updateCalls, 0);
    });

    testWidgets('member sees read-only banner, hides admin actions, and shows inline banner on 403', (tester) async {
      final repo = FakeGroupRepository()
        ..detailGroup = _sampleGroup(myRole: GroupRole.member);

      final container = ProviderContainer(
        overrides: [
          groupRepositoryProvider.overrideWithValue(repo),
          profileRepositoryProvider.overrideWithValue(
            _StubProfileRepo(const UserProfile(id: 'member-1', email: 'm@t')),
          ),
        ],
      );
      addTearDown(container.dispose);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(home: GroupDetailScreen(groupId: 'g-1')),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('group_member_readonly_banner')), findsOneWidget);
      expect(find.byKey(const Key('group_edit_button')), findsNothing);
      expect(find.byKey(const Key('group_add_member_button')), findsNothing);
      expect(find.byKey(const Key('group_remove_member_btn_admin-1')), findsNothing);

      repo.mutationError = _httpError(403, 'Chỉ quản trị viên nhóm mới có quyền');
      await container
          .read(groupDetailProvider.notifier)
          .updateGroup('g-1', const UpdateGroupRequest(name: 'Hack'));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('group_detail_action_error_banner')), findsOneWidget);
    });

    testWidgets('TripListScreen and TripDetailScreen navigate to /groups', (tester) async {
      final groupRepo = FakeGroupRepository();
      final tripRepo = _StubTripRepo();

      final router = GoRouter(
        initialLocation: '/trips',
        routes: [
          GoRoute(path: '/trips', builder: (_, __) => const TripListScreen()),
          GoRoute(
            path: '/trips/:id',
            builder: (_, s) => TripDetailScreen(tripId: s.pathParameters['id']!),
          ),
          GoRoute(
            path: '/groups',
            builder: (_, s) => GroupListScreen(
              initialTripId: s.uri.queryParameters['tripId'],
            ),
          ),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            groupRepositoryProvider.overrideWithValue(groupRepo),
            tripRepositoryProvider.overrideWithValue(tripRepo),
          ],
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('trip_list_groups_button')));
      await tester.pumpAndSettle();
      expect(find.text('Nhóm chuyến đi'), findsOneWidget);

      router.go('/trips/trip-1');
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('trip_detail_open_groups_button')));
      await tester.pumpAndSettle();
      expect(find.text('Nhóm chuyến đi'), findsOneWidget);
    });
  });
}
