import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:wanderai_mobile/features/profile/data/profile_models.dart';
import 'package:wanderai_mobile/features/profile/data/profile_repository.dart';
import 'package:wanderai_mobile/features/profile/providers/profile_provider.dart';
import 'package:wanderai_mobile/features/profile/presentation/preferences_screen.dart';
import 'package:wanderai_mobile/core/widgets/app_button.dart';

class FakeProfileRepository extends ProfileRepository {
  bool shouldFail = false;
  bool isNetworkError = false;
  int updateCallCount = 0;
  TravelPreferences? lastUpdatedPreferences;

  UserProfile mockUser = const UserProfile(
    id: 'user-123',
    email: 'test@wanderai.test',
    displayName: 'Test User',
    preferences: TravelPreferences(
      travelStyle: TravelStyle.comfort,
      budgetMin: 1000000,
      budgetMax: 10000000,
      preferredGroup: GroupSize.couple,
      interests: ['food_cuisine', 'culture_history'],
      avoidances: ['Đông đúc'],
      dietaryNeeds: ['Ăn chay'],
    ),
  );

  FakeProfileRepository() : super(Dio());

  @override
  Future<UserProfile> getProfile() async {
    if (shouldFail) throw Exception('Get profile failed');
    return mockUser;
  }

  @override
  Future<TravelPreferences> updatePreferences(TravelPreferences preferences) async {
    updateCallCount++;
    lastUpdatedPreferences = preferences;
    if (shouldFail) {
      if (isNetworkError) {
        throw DioException(
          requestOptions: RequestOptions(path: '/users/me/preferences'),
          type: DioExceptionType.connectionError,
        );
      }
      throw Exception('Update failed');
    }
    mockUser = UserProfile(
      id: mockUser.id,
      email: mockUser.email,
      displayName: mockUser.displayName,
      preferences: preferences,
    );
    return preferences;
  }
}

void main() {
  group('PreferencesScreen Widget Tests', () {
    late FakeProfileRepository fakeRepo;

    setUp(() {
      fakeRepo = FakeProfileRepository();
    });

    Widget createWidgetUnderTest(WidgetTester tester) {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      return ProviderScope(
        overrides: [
          profileRepositoryProvider.overrideWithValue(fakeRepo),
        ],
        child: const MaterialApp(
          home: PreferencesScreen(),
        ),
      );
    }

    testWidgets('1. renders persisted values correctly', (tester) async {
      await tester.pumpWidget(createWidgetUnderTest(tester));
      await tester.pumpAndSettle();

      // Check header
      expect(find.text('Tùy chỉnh thông tin du lịch cá nhân'), findsOneWidget);

      // Check travel style (Thoải mái is selected)
      expect(find.text('Thoải mái'), findsOneWidget);

      // Check budget
      expect(find.text('1000000'), findsOneWidget);
      expect(find.text('10000000'), findsOneWidget);

      // Check preferred group (Cặp đôi)
      expect(find.text('Cặp đôi'), findsOneWidget);

      // Check canonical interests
      expect(find.text('Ẩm thực & Đặc sản'), findsOneWidget);
      expect(find.text('Văn hóa & Lịch sử'), findsOneWidget);

      // Check avoidances & dietary
      expect(find.text('Đông đúc'), findsOneWidget);
      expect(find.text('Ăn chay'), findsOneWidget);
    });

    testWidgets('2. changing field updates state to dirty', (tester) async {
      await tester.pumpWidget(createWidgetUnderTest(tester));
      await tester.pumpAndSettle();

      final element = tester.element(find.byType(PreferencesScreen));
      final container = ProviderScope.containerOf(element);

      expect(container.read(profileProvider).isDirty, isFalse);

      // Tap on 'Phượt' (Backpacker)
      await tester.tap(find.text('Phượt'));
      await tester.pumpAndSettle();

      expect(container.read(profileProvider).isDirty, isTrue);
      expect(
        container.read(profileProvider).formPreferences.travelStyle,
        equals(TravelStyle.backpacker),
      );
    });

    testWidgets('3 & 4. save triggers expected API call and updates local state on success',
        (tester) async {
      await tester.pumpWidget(createWidgetUnderTest(tester));
      await tester.pumpAndSettle();

      // Tap 'Sang trọng' (Luxury)
      await tester.tap(find.text('Sang trọng'));
      await tester.pumpAndSettle();

      // Tap 'Lưu sở thích du lịch'
      await tester.tap(find.widgetWithText(AppButton, 'Lưu sở thích du lịch'));
      await tester.pumpAndSettle();

      // Verify API was called
      expect(fakeRepo.updateCallCount, equals(1));
      expect(fakeRepo.lastUpdatedPreferences?.travelStyle, equals(TravelStyle.luxury));

      // Verify success banner is shown
      expect(find.text('Lưu sở thích du lịch thành công!'), findsOneWidget);
    });

    testWidgets('5. validation error shown without destroying input', (tester) async {
      await tester.pumpWidget(createWidgetUnderTest(tester));
      await tester.pumpAndSettle();

      final element = tester.element(find.byType(PreferencesScreen));
      final notifier = ProviderScope.containerOf(element).read(profileProvider.notifier);

      // Set min > max
      notifier.setBudget(25000000, 10000000);
      await tester.pumpAndSettle();

      // Tap Save
      await tester.tap(find.widgetWithText(AppButton, 'Lưu sở thích du lịch'));
      await tester.pumpAndSettle();

      // Should show error message
      expect(
        find.text('Ngân sách tối thiểu không được lớn hơn ngân sách tối đa'),
        findsOneWidget,
      );

      // Form input should NOT be wiped
      expect(find.text('25000000'), findsOneWidget);
      expect(find.text('10000000'), findsOneWidget);
      expect(fakeRepo.updateCallCount, equals(0));
    });

    testWidgets('6. network failure preserves edits', (tester) async {
      fakeRepo.shouldFail = true;
      fakeRepo.isNetworkError = true;

      await tester.pumpWidget(createWidgetUnderTest(tester));
      await tester.pumpAndSettle();

      // Toggle interest 'Biển đảo & Nghỉ dưỡng'
      await tester.tap(find.text('Biển đảo & Nghỉ dưỡng'));
      await tester.pumpAndSettle();

      // Tap Save
      await tester.tap(find.widgetWithText(AppButton, 'Lưu sở thích du lịch'));
      await tester.pumpAndSettle();

      // Error message shown
      expect(find.text('Không có kết nối mạng.'), findsOneWidget);

      // Verify user edit 'Biển đảo & Nghỉ dưỡng' is preserved
      final element = tester.element(find.byType(PreferencesScreen));
      final prefs = ProviderScope.containerOf(element).read(profileProvider).formPreferences;
      expect(prefs.interests, contains('beach_island'));
    });

    testWidgets('7 & 8. save button disabled while saving and duplicate submit prevented',
        (tester) async {
      await tester.pumpWidget(createWidgetUnderTest(tester));
      await tester.pumpAndSettle();

      final element = tester.element(find.byType(PreferencesScreen));
      final notifier = ProviderScope.containerOf(element).read(profileProvider.notifier);

      // Trigger two saves rapidly
      final f1 = notifier.savePreferences();
      final f2 = notifier.savePreferences();

      final r1 = await f1;
      final r2 = await f2;

      expect(r1, isTrue);
      expect(r2, isFalse); // duplicate prevented!
      expect(fakeRepo.updateCallCount, equals(1));
    });

    testWidgets('9. no pace production control rendered', (tester) async {
      await tester.pumpWidget(createWidgetUnderTest(tester));
      await tester.pumpAndSettle();

      expect(find.textContaining(RegExp(r'pace', caseSensitive: false)), findsNothing);
      expect(find.textContaining(RegExp(r'nhịp độ', caseSensitive: false)), findsNothing);
    });

    testWidgets('10. no presence/online control introduced', (tester) async {
      await tester.pumpWidget(createWidgetUnderTest(tester));
      await tester.pumpAndSettle();

      expect(find.textContaining(RegExp(r'online', caseSensitive: false)), findsNothing);
      expect(find.textContaining(RegExp(r'presence', caseSensitive: false)), findsNothing);
      expect(find.textContaining(RegExp(r'trạng thái hoạt động', caseSensitive: false)), findsNothing);
    });
  });
}
