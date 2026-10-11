import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/core/widgets/widgets.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/map/data/place_repository.dart';
import 'package:wanderai_mobile/features/map/providers/map_provider.dart';

class FakePlaceRepository implements PlaceRepository {
  List<PlaceModel> nearbyResults = [];
  List<PlaceModel> searchResults = [];

  @override
  Future<List<PlaceModel>> getNearby({
    required double lat,
    required double lng,
    double radiusKm = 10.0,
    int limit = 100,
    String? category,
    bool verifiedOnly = true,
  }) async {
    return nearbyResults;
  }

  @override
  Future<List<PlaceModel>> getPlaces({
    int page = 1,
    int limit = 50,
    String? search,
    String? category,
    String? destinationId,
    bool verifiedOnly = true,
  }) async {
    return searchResults;
  }

  @override
  Future<PlaceModel> getPlaceById(String id) async {
    throw UnimplementedError();
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('GoMate Design System Tokens', () {
    test('1. AppColors conforms to GoMate UX spec v1', () {
      expect(AppColors.primary, const Color(0xFF0F766E));
      expect(AppColors.primaryContainer, const Color(0xFFCCFBF1));
      expect(AppColors.onPrimary, const Color(0xFFFFFFFF));
      expect(AppColors.background, const Color(0xFFF8FAFC));
      expect(AppColors.surface, const Color(0xFFFFFFFF));
      expect(AppColors.textPrimary, const Color(0xFF0F172A));
      expect(AppColors.textSecondary, const Color(0xFF475569));
      expect(AppColors.border, const Color(0xFFE2E8F0));
      expect(AppColors.success, const Color(0xFF15803D));
      expect(AppColors.warning, const Color(0xFFB45309));
      expect(AppColors.error, const Color(0xFFB91C1C));
      expect(AppColors.info, const Color(0xFF2563EB));
    });

    test('2. AppColors.forCategory returns appropriate category semantic colors', () {
      expect(AppColors.forCategory('attraction'), AppColors.catAttraction);
      expect(AppColors.forCategory('Tham quan'), AppColors.catAttraction);
      expect(AppColors.forCategory('restaurant'), AppColors.catRestaurant);
      expect(AppColors.forCategory('beach'), AppColors.catBeach);
      expect(AppColors.forCategory('culture'), AppColors.catCulture);
      expect(AppColors.forCategory('nature'), AppColors.catNature);
      expect(AppColors.forCategory('cafe'), AppColors.catCafe);
      expect(AppColors.forCategory('hotel'), AppColors.catHotel);
      expect(AppColors.forCategory('unknown'), AppColors.primary);
    });

    test('3. AppSpacing follows 4px base grid', () {
      expect(AppSpacing.xs, 4.0);
      expect(AppSpacing.sm, 8.0);
      expect(AppSpacing.mdSmall, 12.0);
      expect(AppSpacing.md, 16.0);
      expect(AppSpacing.lgSmall, 20.0);
      expect(AppSpacing.lg, 24.0);
      expect(AppSpacing.xl, 32.0);
      expect(AppSpacing.xxl, 40.0);
      expect(AppSpacing.xxxl, 48.0);
    });

    test('4. AppRadius tokens match UX specification', () {
      expect(AppRadius.sm, 8.0);
      expect(AppRadius.md, 12.0);
      expect(AppRadius.card, 16.0);
      expect(AppRadius.hero, 20.0);
      expect(AppRadius.sheet, 24.0);
      expect(AppRadius.pill, 999.0);
    });

    test('5. AppTheme builds lightTheme without errors', () {
      final theme = AppTheme.lightTheme;
      expect(theme.colorScheme.primary, AppColors.primary);
      expect(theme.scaffoldBackgroundColor, AppColors.background);
      expect(theme.cardTheme.color, AppColors.surface);
    });
  });

  group('GoMate Shared Reusable Components', () {
    testWidgets('6. RatingView honestly handles null, 0.0, and real ratings', (tester) async {
      // Null rating -> "Chưa có đánh giá"
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: RatingView(rating: null)),
        ),
      );
      expect(find.text('Chưa có đánh giá'), findsOneWidget);
      expect(find.text('0.0'), findsNothing);
      expect(find.text('4.5'), findsNothing);

      // 0.0 rating -> "Chưa có đánh giá"
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: RatingView(rating: 0.0)),
        ),
      );
      expect(find.text('Chưa có đánh giá'), findsOneWidget);

      // Real rating 4.8 with 25 reviews
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: RatingView(rating: 4.8, reviewCount: 25)),
        ),
      );
      expect(find.text('4.8'), findsOneWidget);
      expect(find.text('(25)'), findsOneWidget);
      expect(find.text('Chưa có đánh giá'), findsNothing);
    });

    testWidgets('7. AppBadge.verified displays checkmark and "Đã xác minh"', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: AppBadge.verified()),
        ),
      );
      expect(find.text('Đã xác minh'), findsOneWidget);
      expect(find.byIcon(Icons.verified), findsOneWidget);
    });

    testWidgets('8. AppButton renders label and handles tap and loading state', (tester) async {
      bool tapped = false;

      // Normal state
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppButton(
              text: 'Lập lịch trình bằng AI',
              onPressed: () => tapped = true,
              variant: AppButtonVariant.ai,
            ),
          ),
        ),
      );
      expect(find.text('Lập lịch trình bằng AI'), findsOneWidget);
      expect(find.byIcon(Icons.auto_awesome), findsOneWidget);
      await tester.tap(find.text('Lập lịch trình bằng AI'));
      expect(tapped, isTrue);

      // Loading state
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AppButton(
              text: 'Lập lịch trình bằng AI',
              isLoading: true,
            ),
          ),
        ),
      );
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Lập lịch trình bằng AI'), findsNothing);
    });

    testWidgets('9. AppEmptyState and AppErrorState render correctly with actions', (tester) async {
      bool retryClicked = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppErrorState(
              title: 'Lỗi kết nối',
              message: 'Không thể kết nối đến máy chủ.',
              onRetry: () => retryClicked = true,
            ),
          ),
        ),
      );
      expect(find.text('Lỗi kết nối'), findsOneWidget);
      expect(find.text('Không thể kết nối đến máy chủ.'), findsOneWidget);
      expect(find.text('Thử lại'), findsOneWidget);
      await tester.tap(find.text('Thử lại'));
      expect(retryClicked, isTrue);

      // Empty State
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AppEmptyState(
              title: 'Chưa có chuyến đi',
              description: 'Tạo chuyến đi đầu tiên để Wandy giúp bạn lập lịch.',
              actionLabel: 'Tạo chuyến đi',
              onAction: () {},
            ),
          ),
        ),
      );
      expect(find.text('Chưa có chuyến đi'), findsOneWidget);
      expect(find.text('Tạo chuyến đi đầu tiên để Wandy giúp bạn lập lịch.'), findsOneWidget);
      expect(find.text('Tạo chuyến đi'), findsOneWidget);
    });

    testWidgets('10. ResponsiveWrapper enforces maxWidth constraints on wide viewport', (tester) async {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.resetPhysicalSize());

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ResponsiveWrapper(
              maxWidth: 640.0,
              child: SizedBox(height: 100, child: Text('Responsive Content')),
            ),
          ),
        ),
      );

      final constrainedBoxFinder = find.descendant(
        of: find.byType(ResponsiveWrapper),
        matching: find.byType(ConstrainedBox),
      );
      final constrainedBox = tester.widget<ConstrainedBox>(constrainedBoxFinder);
      expect(constrainedBox.constraints.maxWidth, 640.0);
    });
  });

  group('Map UX Stability & Stale Sheet Fixes', () {
    test('11. MapNotifier clears selectedPlace when category filter changes', () async {
      final fakeRepo = FakePlaceRepository();
      const samplePlace1 = PlaceModel(
        id: 'place-1',
        name: 'Nhà hàng Bếp Xưa',
        categoryName: 'restaurant',
        latitude: 21.02,
        longitude: 105.85,
        isVerified: true,
      );
      const samplePlace2 = PlaceModel(
        id: 'place-2',
        name: 'Khách sạn Mường Thanh',
        categoryName: 'hotel',
        latitude: 21.03,
        longitude: 105.84,
        isVerified: true,
      );
      fakeRepo.nearbyResults = [samplePlace1, samplePlace2];

      final container = ProviderContainer(
        overrides: [
          placeRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      final notifier = container.read(mapProvider.notifier);

      // Load nearby and select place 1
      await notifier.loadNearby(center: const LatLng(21.02, 105.85));
      notifier.selectPlace(samplePlace1);
      expect(container.read(mapProvider).selectedPlace?.id, 'place-1');

      // Now change category to 'hotel' -> selectedPlace MUST BE CLEARED
      notifier.setCategory('hotel');
      expect(container.read(mapProvider).selectedPlace, isNull);
    });

    test('12. MapNotifier clears selectedPlace when searching or clearing search', () async {
      final fakeRepo = FakePlaceRepository();
      const samplePlace = PlaceModel(
        id: 'place-1',
        name: 'Chùa Một Cột',
        categoryName: 'culture',
        latitude: 21.035,
        longitude: 105.833,
        isVerified: true,
      );
      fakeRepo.searchResults = [samplePlace];

      final container = ProviderContainer(
        overrides: [
          placeRepositoryProvider.overrideWithValue(fakeRepo),
        ],
      );

      final notifier = container.read(mapProvider.notifier);
      notifier.selectPlace(samplePlace);
      expect(container.read(mapProvider).selectedPlace?.id, 'place-1');

      // Search query triggers clear
      await notifier.searchPlaces('Chùa');
      expect(container.read(mapProvider).selectedPlace, isNull);

      // Re-select and clear search -> MUST BE CLEARED
      notifier.selectPlace(samplePlace);
      await notifier.searchPlaces('');
      expect(container.read(mapProvider).selectedPlace, isNull);
    });
  });
}
