import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wanderai_mobile/core/router/app_router.dart';
import 'package:wanderai_mobile/features/auth/data/auth_models.dart';
import 'package:wanderai_mobile/features/auth/data/auth_repository.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/profile/data/profile_models.dart';
import 'package:wanderai_mobile/features/profile/data/profile_repository.dart';
import 'package:wanderai_mobile/features/profile/providers/profile_provider.dart';

/// Shared fake "server session": which user the current token belongs to.
class _Session {
  String? userId;
}

class _FakeAuthRepo extends AuthRepository {
  final _Session session;
  final Map<String, String> emailToUserId;
  _FakeAuthRepo(this.session, this.emailToUserId) : super(Dio());

  @override
  Future<bool> restoreSession() async => session.userId != null;

  @override
  Future<AuthTokens> login(LoginRequest request) async {
    session.userId = emailToUserId[request.email];
    return const AuthTokens(accessToken: 't', refreshToken: 'r');
  }

  @override
  Future<void> logout() async {
    session.userId = null;
  }
}

class _FakeProfileRepo extends ProfileRepository {
  final _Session session;
  final Map<String, UserProfile> users;
  _FakeProfileRepo(this.session, this.users) : super(Dio());

  @override
  Future<UserProfile> getProfile() async {
    final id = session.userId;
    if (id == null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/users/me'),
        response: Response(requestOptions: RequestOptions(path: '/users/me'), statusCode: 401),
        type: DioExceptionType.badResponse,
      );
    }
    return users[id]!;
  }
}

Future<void> settle() => Future<void>.delayed(const Duration(milliseconds: 20));

void main() {
  group('G-01 profile state isolation across logout / account switch', () {
    test('User A prefs never appear for User B', () async {
      final session = _Session()..userId = 'user-a';
      const userA = UserProfile(
        id: 'user-a',
        email: 'a@test',
        preferences: TravelPreferences(
          interests: ['culture_history', 'food_cuisine'],
          avoidances: ['Đông đúc'],
          budgetMin: 111,
          budgetMax: 999,
        ),
      );
      const userB = UserProfile(
        id: 'user-b',
        email: 'b@test',
        preferences: TravelPreferences(interests: ['beach_island']),
      );
      final users = {'user-a': userA, 'user-b': userB};

      final container = ProviderContainer(overrides: [
        authRepositoryProvider.overrideWithValue(_FakeAuthRepo(session, {'a@test': 'user-a', 'b@test': 'user-b'})),
        profileRepositoryProvider.overrideWithValue(_FakeProfileRepo(session, users)),
      ]);
      addTearDown(container.dispose);

      // The router notifier owns the auth listener that resets session-scoped state.
      container.read(routerNotifierProvider);
      await settle();
      expect(container.read(authProvider).status, AuthStatus.authenticated);

      // User A loads preferences.
      container.read(profileProvider);
      await settle();
      expect(container.read(profileProvider).user!.id, 'user-a');
      expect(container.read(profileProvider).formPreferences.interests, ['culture_history', 'food_cuisine']);

      // Logout: A's state must be gone immediately.
      await container.read(authProvider.notifier).logout();
      await settle();
      final afterLogout = container.read(profileProvider);
      expect(afterLogout.user, isNull);
      expect(afterLogout.persistedPreferences, isNull);
      expect(afterLogout.formPreferences.interests, isEmpty);
      expect(afterLogout.formPreferences.avoidances, isEmpty);
      expect(afterLogout.formPreferences.budgetMax, isNot(999));

      // User B logs in: only B's data is visible.
      expect(await container.read(authProvider.notifier).login('b@test', 'pw'), isTrue);
      await settle();
      container.read(profileProvider); // recreated lazily with B's session
      await settle();
      final b = container.read(profileProvider);
      expect(b.user!.id, 'user-b');
      expect(b.formPreferences.interests, ['beach_island']);
      expect(b.formPreferences.interests, isNot(contains('culture_history')));
      expect(b.formPreferences.avoidances, isEmpty);
      expect(b.formPreferences.budgetMin, 0);
    });
  });

  group('G-04 legacy non-canonical interests', () {
    test('fromJson drops legacy values deterministically (order kept, deduped)', () {
      final p = TravelPreferences.fromJson({
        'travelStyle': 'COMFORT',
        'interests': ['beach', 'food_cuisine', 'Culture', 'culture_history', 'food_cuisine', ' nature_outdoor '],
      });
      expect(p.interests, ['food_cuisine', 'culture_history', 'nature_outdoor']);
    });

    test('toJson never sends a non-canonical interest, so save cannot 400 on legacy data', () {
      const dirty = TravelPreferences(interests: ['mountain', 'coffee_culture', 'legacy_x']);
      expect(dirty.toJson()['interests'], ['coffee_culture']);
    });

    test('canonical contract is exactly the 7 keys', () {
      expect(kCanonicalInterestKeys, {
        'food_cuisine',
        'culture_history',
        'nature_outdoor',
        'coffee_culture',
        'beach_island',
        'shopping_local',
        'nightlife_entertainment',
      });
    });

    test('a stored legacy row stays savable: load -> save sends only canonical interests', () async {
      final session = _Session()..userId = 'u';
      final users = {
        'u': UserProfile.fromJson({
          'id': 'u',
          'email': 'u@test',
          'preferences': {
            'travelStyle': 'COMFORT',
            'interests': ['beach', 'culture_history'],
          },
        }),
      };
      final saved = <Map<String, dynamic>>[];
      final repo = _SavingProfileRepo(session, users, saved);
      final container = ProviderContainer(overrides: [profileRepositoryProvider.overrideWithValue(repo)]);
      addTearDown(container.dispose);

      container.read(profileProvider);
      await settle();
      expect(container.read(profileProvider).formPreferences.interests, ['culture_history']);
      expect(await container.read(profileProvider.notifier).savePreferences(), isTrue);
      expect(saved.single['interests'], ['culture_history']);
    });
  });
}

class _SavingProfileRepo extends _FakeProfileRepo {
  final List<Map<String, dynamic>> saved;
  _SavingProfileRepo(super.session, super.users, this.saved);

  @override
  Future<TravelPreferences> updatePreferences(TravelPreferences preferences) async {
    saved.add(preferences.toJson());
    return preferences;
  }
}
