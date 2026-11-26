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
import 'package:wanderai_mobile/features/groups/data/group_models.dart';
import 'package:wanderai_mobile/features/groups/data/group_repository.dart';
import 'package:wanderai_mobile/features/groups/presentation/group_detail_screen.dart';
import 'package:wanderai_mobile/features/groups/providers/group_provider.dart';
import 'package:wanderai_mobile/features/profile/data/profile_models.dart';
import 'package:wanderai_mobile/features/profile/data/profile_repository.dart';
import 'package:wanderai_mobile/features/profile/providers/profile_provider.dart';

class _LiveFetchedGroupRepo extends GroupRepository {
  final GroupModel preloaded;
  _LiveFetchedGroupRepo(super.dio, this.preloaded);

  @override
  Future<GroupModel> getGroup(String id) async => preloaded;
}

class _LiveFetchedProfileRepo extends ProfileRepository {
  final UserProfile preloaded;
  _LiveFetchedProfileRepo(super.dio, this.preloaded);

  @override
  Future<UserProfile> getProfile() async => preloaded;
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

  final live = Platform.environment['LIVE_W09A_E2E'] == '1';
  final baseUrl =
      Platform.environment['LIVE_API_BASE_URL'] ?? 'http://127.0.0.1:3000';

  group(
    'W09-A Live Flutter -> NestJS -> PostgreSQL (wanderai_w09a_test)',
    () {
      late String groupId;
      late String adminUserId;
      late String memberUserId;
      late String adminAccessToken;
      late String adminRefreshToken;
      late String memberAccessToken;
      late String memberRefreshToken;

      test(
        '3-actor live journey: admin create/add/update persisted across cold container recreate; member 403 + DB unchanged; outsider 403',
        () async {
          final stamp = DateTime.now().millisecondsSinceEpoch;
          final adminEmail = 'w09a_fl_admin_$stamp@gomate.vn';
          final memberEmail = 'w09a_fl_member_$stamp@gomate.vn';
          final outsiderEmail = 'w09a_fl_outsider_$stamp@gomate.vn';
          const password = 'W09aPass#2026';

          // 1. Register Actor B (Member) and get their userId
          SharedPreferences.setMockInitialValues({});
          final memberSetup = _buildLiveContainer(baseUrl);
          memberSetup.read(routerNotifierProvider);
          await _waitForAuthSettled(memberSetup);
          final memberRegistered = await memberSetup
              .read(authProvider.notifier)
              .register('Thành Viên Live', memberEmail, password);
          expect(memberRegistered, isTrue);
          final memberRes = await memberSetup
              .read(apiClientProvider)
              .get('/users/me');
          memberUserId = (memberRes.data['data']['id'] as String);
          final memberPrefs = await SharedPreferences.getInstance();
          memberAccessToken = memberPrefs.getString('access_token')!;
          memberRefreshToken = memberPrefs.getString('refresh_token')!;
          memberSetup.dispose();

          // 2. Register Actor C (Outsider)
          SharedPreferences.setMockInitialValues({});
          final outsiderSetup = _buildLiveContainer(baseUrl);
          outsiderSetup.read(routerNotifierProvider);
          await _waitForAuthSettled(outsiderSetup);
          final outsiderRegistered = await outsiderSetup
              .read(authProvider.notifier)
              .register('Người Ngoài Live', outsiderEmail, password);
          expect(outsiderRegistered, isTrue);
          final outsiderPrefs = await SharedPreferences.getInstance();
          final outsiderAccess = outsiderPrefs.getString('access_token')!;
          final outsiderRefresh = outsiderPrefs.getString('refresh_token')!;
          outsiderSetup.dispose();

          // 3. Register Actor A (Admin), create group, view members, add Actor B, rename group
          SharedPreferences.setMockInitialValues({});
          final adminContainer1 = _buildLiveContainer(baseUrl);
          adminContainer1.read(routerNotifierProvider);
          await _waitForAuthSettled(adminContainer1);
          final adminRegistered = await adminContainer1
              .read(authProvider.notifier)
              .register('Trưởng Nhóm Live', adminEmail, password);
          expect(adminRegistered, isTrue);
          final adminMe = await adminContainer1
              .read(apiClientProvider)
              .get('/users/me');
          adminUserId = adminMe.data['data']['id'] as String;
          final adminPrefs = await SharedPreferences.getInstance();
          adminAccessToken = adminPrefs.getString('access_token')!;
          adminRefreshToken = adminPrefs.getString('refresh_token')!;

          final created = await adminContainer1
              .read(groupListProvider.notifier)
              .createGroup(
                const CreateGroupRequest(
                  name: 'Nhóm Hạ Long Live Test',
                  description: 'Kiểm thử Flutter -> PostgreSQL',
                ),
              );
          expect(created, isNotNull);
          groupId = created!.id;
          expect(created.myRole, GroupRole.admin);

          await adminContainer1
              .read(groupDetailProvider.notifier)
              .loadGroup(groupId);
          expect(adminContainer1.read(groupDetailProvider).group?.memberCount, 1);

          final added = await adminContainer1
              .read(groupDetailProvider.notifier)
              .addMember(groupId, memberUserId);
          expect(added, isTrue);

          final renamed = await adminContainer1
              .read(groupDetailProvider.notifier)
              .updateGroup(
                groupId,
                const UpdateGroupRequest(
                  name: 'Nhóm Hạ Long Đã Lưu PostgreSQL',
                ),
              );
          expect(renamed, isTrue);
          adminContainer1.dispose();

          // 4. Cold-recreate Admin container to prove PostgreSQL persistence
          SharedPreferences.setMockInitialValues({
            'access_token': adminAccessToken,
            'refresh_token': adminRefreshToken,
          });
          final adminContainer2 = _buildLiveContainer(baseUrl);
          adminContainer2.read(routerNotifierProvider);
          await _waitForAuthSettled(adminContainer2);
          await adminContainer2
              .read(groupDetailProvider.notifier)
              .loadGroup(groupId);
          final persistedGroup =
              adminContainer2.read(groupDetailProvider).group;
          expect(persistedGroup, isNotNull);
          expect(persistedGroup!.name, 'Nhóm Hạ Long Đã Lưu PostgreSQL');
          expect(persistedGroup.memberCount, 2);
          expect(
            persistedGroup.members.any((m) => m.userId == memberUserId),
            isTrue,
          );
          adminContainer2.dispose();

          // 5. Actor B (Member): views group OK, privileged actions return 403, DB unchanged
          SharedPreferences.setMockInitialValues({
            'access_token': memberAccessToken,
            'refresh_token': memberRefreshToken,
          });
          final memberContainer = _buildLiveContainer(baseUrl);
          memberContainer.read(routerNotifierProvider);
          await _waitForAuthSettled(memberContainer);
          await memberContainer
              .read(groupDetailProvider.notifier)
              .loadGroup(groupId);
          expect(
            memberContainer.read(groupDetailProvider).group?.myRole,
            GroupRole.member,
          );

          final memberPatchOk = await memberContainer
              .read(groupDetailProvider.notifier)
              .updateGroup(
                groupId,
                const UpdateGroupRequest(name: 'Member Hacked Live'),
              );
          expect(memberPatchOk, isFalse);
          expect(
            memberContainer.read(groupDetailProvider).actionErrorMessage,
            isNotNull,
          );

          final memberDeleteOk = await memberContainer
              .read(groupDetailProvider.notifier)
              .removeMember(groupId, adminUserId);
          expect(memberDeleteOk, isFalse);

          // Reload from PostgreSQL to verify unchanged
          await memberContainer
              .read(groupDetailProvider.notifier)
              .loadGroup(groupId);
          expect(
            memberContainer.read(groupDetailProvider).group?.name,
            'Nhóm Hạ Long Đã Lưu PostgreSQL',
          );
          expect(
            memberContainer.read(groupDetailProvider).group?.memberCount,
            2,
          );
          memberContainer.dispose();

          // 6. Actor C (Outsider): 403 Forbidden
          SharedPreferences.setMockInitialValues({
            'access_token': outsiderAccess,
            'refresh_token': outsiderRefresh,
          });
          final outsiderContainer = _buildLiveContainer(baseUrl);
          outsiderContainer.read(routerNotifierProvider);
          await _waitForAuthSettled(outsiderContainer);
          await outsiderContainer
              .read(groupDetailProvider.notifier)
              .loadGroup(groupId);
          expect(outsiderContainer.read(groupDetailProvider).isForbidden, isTrue);
          expect(outsiderContainer.read(groupDetailProvider).group, isNull);
          outsiderContainer.dispose();
        },
      );

      testWidgets(
        'Widget rendering against live NestJS: GroupDetailScreen displays real PostgreSQL members & role badges',
        (tester) async {
          SharedPreferences.setMockInitialValues({
            'access_token': adminAccessToken,
            'refresh_token': adminRefreshToken,
          });

          late GroupModel liveGroup;
          late UserProfile liveProfile;

          await tester.runAsync(() async {
            final fetchContainer = _buildLiveContainer(baseUrl);
            try {
              await fetchContainer.read(profileProvider.notifier).loadProfile();
              await fetchContainer
                  .read(groupDetailProvider.notifier)
                  .loadGroup(groupId);
              liveGroup = fetchContainer.read(groupDetailProvider).group!;
              liveProfile = fetchContainer.read(profileProvider).user!;
            } finally {
              fetchContainer.dispose();
            }
          });

          await tester.pumpWidget(
            ProviderScope(
              overrides: [
                groupRepositoryProvider.overrideWith(
                  (ref) => _LiveFetchedGroupRepo(
                    ref.read(apiClientProvider),
                    liveGroup,
                  ),
                ),
                profileRepositoryProvider.overrideWith(
                  (ref) => _LiveFetchedProfileRepo(
                    ref.read(apiClientProvider),
                    liveProfile,
                  ),
                ),
              ],
              child: MaterialApp(
                home: GroupDetailScreen(groupId: groupId),
              ),
            ),
          );
          await tester.pumpAndSettle();

          expect(find.text('Nhóm Hạ Long Đã Lưu PostgreSQL'), findsWidgets);
          expect(find.text('Trưởng Nhóm Live (Bạn)'), findsOneWidget);
          expect(find.text('Thành Viên Live'), findsOneWidget);
          expect(find.text('Trưởng nhóm (admin)'), findsWidgets);
          expect(find.text('Thành viên (member)'), findsOneWidget);
          expect(find.textContaining('@'), findsNothing);
        },
      );
    },
    skip: live ? false : 'Set LIVE_W09A_E2E=1 to run against live NestJS + PostgreSQL',
  );
}
