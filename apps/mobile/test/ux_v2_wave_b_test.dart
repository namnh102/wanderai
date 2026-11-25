import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/core/widgets/app_state_banner.dart';
import 'package:wanderai_mobile/features/ai_chat/providers/chat_provider.dart';
import 'package:wanderai_mobile/features/auth/presentation/login_screen.dart';
import 'package:wanderai_mobile/features/auth/presentation/register_screen.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/map_category_bar.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/map_destination_selector.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/place_preview_sheet.dart';
import 'package:wanderai_mobile/features/places/presentation/place_detail_screen.dart';
import 'package:wanderai_mobile/features/places/providers/place_detail_provider.dart';
import 'package:wanderai_mobile/features/recommendations/data/recommendation_models.dart';
import 'package:wanderai_mobile/features/recommendations/data/recommendation_repository.dart';
import 'package:wanderai_mobile/features/recommendations/presentation/recommendation_screen.dart';
import 'package:wanderai_mobile/features/trips/data/trip_models.dart';
import 'package:wanderai_mobile/features/trips/data/trip_repository.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_detail_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_list_screen.dart';
import 'package:wanderai_mobile/features/trips/providers/trip_provider.dart';

import 'location_navigation_test.dart' show FakeLocationService;

class _FakeRecoRepo extends Fake implements RecommendationRepository {
  final RecommendationResult Function(String destination) builder;
  _FakeRecoRepo(this.builder);

  @override
  Future<RecommendationResult> fetch({
    required String destination,
    int topK = RecommendationRepository.defaultTopK,
    String model = RecommendationRepository.defaultModel,
  }) async =>
      builder(destination);
}

class _FakeTripRepo extends Fake implements TripRepository {
  final List<TripModel> trips;
  final TripModel? detail;

  _FakeTripRepo({this.trips = const [], this.detail});

  @override
  Future<List<TripModel>> getMyTrips() async => trips;

  @override
  Future<TripModel> getTripDetail(String id) async =>
      detail ??
      TripModel(
        id: id,
        userId: 'u1',
        title: 'Khám phá Đà Nẵng',
        status: 'PLANNED',
      );
}

PlaceModel _samplePlace({double? rating, int reviewCount = 0}) => PlaceModel.fromJson({
      'id': 'p-wb-1',
      'name': 'Bảo tàng Chăm & Không gian Di sản Miền Trung',
      'nameEn': 'Cham Museum',
      'address': 'Số 2 Đường 2/9, Hải Châu, Đà Nẵng',
      'latitude': 16.0605,
      'longitude': 108.2234,
      'rating': rating,
      'reviewCount': reviewCount,
      'isVerified': true,
      'openingHours': 'Mo-Su 07:30-17:00',
      'category': {'name': 'culture'},
      'destination': {'name': 'Đà Nẵng'},
      'source': {
        'name': 'OpenStreetMap',
        'canonicalUrl': 'https://www.openstreetmap.org/node/99',
        'license': 'ODbL 1.0',
      },
    });

RecommendationResult _sampleRecoResult(String slug, {bool coldStart = false}) {
  return RecommendationResult.fromJson({
    'recommendations': [
      {
        'place_id': 'p-1',
        'name': 'Bảo tàng Mỹ thuật Đà Nẵng',
        'destination': 'Đà Nẵng',
        'destination_slug': slug,
        'category': 'culture',
        'score': 0.88,
        'rank': 1,
        'matched_interests': ['culture_history'],
        'explanation': {
          'reason_code': 'PREFERENCE_TAXONOMY_MATCH',
          'matched_interests': ['culture_history'],
          'matched_taxonomy': ['CULTURE_HERITAGE'],
          'text': 'Phù hợp với sở thích văn hóa & lịch sử của bạn.',
        },
        'strategy': 'rec-a1_content_match',
      },
      {
        'place_id': 'p-2',
        'name': 'Quán Cà phê Sông Hàn View Cầu Rồng',
        'destination': 'Đà Nẵng',
        'destination_slug': slug,
        'category': 'cafe',
        'score': 0.76,
        'rank': 2,
        'matched_interests': ['coffee_culture'],
        'explanation': {
          'reason_code': 'PREFERENCE_TAXONOMY_MATCH',
          'matched_interests': ['coffee_culture'],
          'matched_taxonomy': ['CAFE_BAKERY'],
          'text': 'Không gian thưởng thức cà phê địa phương thư giãn.',
        },
        'strategy': 'rec-a1_content_match',
      },
    ],
    'metadata': {
      'model': 'rec-a1',
      'destination_filter': slug,
      'total_candidates': 120,
      'returned_count': 2,
      'cold_start': coldStart,
    },
    'unsupported_user_features': <dynamic>[],
  });
}

void _setViewport(WidgetTester tester, Size size) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  });
}

Widget _scaledHost({
  required Widget child,
  double textScale = 1.0,
  List<Override> overrides = const [],
}) {
  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(
      theme: AppTheme.lightTheme,
      home: MediaQuery(
        data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
        child: child,
      ),
    ),
  );
}

void main() {
  group('Wave B — Map Chips & Preview Sheet (P1-MAP-01 + 1.3x)', () {
    testWidgets('MapCategoryBar disables FilterChip checkmark and has zero overflow at 360x800 @ 1.3x',
        (tester) async {
      _setViewport(tester, const Size(360, 800));
      await tester.pumpWidget(
        _scaledHost(
          textScale: 1.3,
          child: Scaffold(
            body: Column(
              children: [
                MapDestinationSelector(
                  selectedSlug: 'ha-noi',
                  onSelected: (_) {},
                ),
                const SizedBox(height: 8),
                MapCategoryBar(
                  selectedCategory: null,
                  onCategorySelected: (_) {},
                ),
              ],
            ),
          ),
        ),
      );

      final allChip = tester.widget<FilterChip>(
        find.ancestor(of: find.text('Tất cả'), matching: find.byType(FilterChip)),
      );
      expect(allChip.showCheckmark, isFalse);

      final destChip = tester.widget<ChoiceChip>(
        find.byKey(const Key('map_destination_chip_ha-noi')),
      );
      expect(destChip.showCheckmark, isFalse);
      expect(find.text('Hà Nội'), findsOneWidget);
      expect(find.text('Tất cả'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('PlacePreviewSheet renders cleanly on 360x800 @ 1.3x scale without overflow',
        (tester) async {
      _setViewport(tester, const Size(360, 800));
      await tester.pumpWidget(
        _scaledHost(
          textScale: 1.3,
          child: Scaffold(
            body: Align(
              alignment: Alignment.bottomCenter,
              child: PlacePreviewSheet(
                place: _samplePlace(rating: null),
                distanceKm: 1.4,
                onClose: () {},
                onViewDetail: () {},
              ),
            ),
          ),
        ),
      );

      expect(find.text('Chưa có đánh giá'), findsOneWidget);
      expect(find.byKey(const Key('place_preview_view_detail')), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });

  group('Wave B — Place Detail V2 + Wandy Handoff + Opt-in GPS', () {
    testWidgets('honest defaults, opt-in GPS button, and safe 360x800 @ 1.3x layout',
        (tester) async {
      _setViewport(tester, const Size(360, 800));
      var gpsClicks = 0;
      var wandyClicks = 0;

      await tester.pumpWidget(
        _scaledHost(
          textScale: 1.3,
          child: Scaffold(
            body: PlaceDetailView(
              place: _samplePlace(rating: null),
              distanceKm: null,
              onOpenUrl: (_) {},
              onDirections: () {},
              onEnableLocation: () => gpsClicks++,
              onAskWandy: () => wandyClicks++,
            ),
          ),
        ),
      );

      expect(find.text('Chưa có đánh giá'), findsOneWidget);
      expect(find.text('Đã xác minh'), findsOneWidget);
      expect(gpsClicks, 0);

      await tester.ensureVisible(find.byKey(const Key('place_detail_enable_location')));
      await tester.tap(find.byKey(const Key('place_detail_enable_location')));
      expect(gpsClicks, 1);

      await tester.tap(find.byKey(const Key('place_detail_ask_wandy')));
      expect(wandyClicks, 1);
      expect(tester.takeException(), isNull);
    });

    testWidgets('PlaceDetailScreen "Hỏi Wandy" sets pendingChatPromptProvider and routes to /ai',
        (tester) async {
      _setViewport(tester, const Size(390, 844));
      final fakeLoc = FakeLocationService();
      late ProviderContainer capturedContainer;

      final router = GoRouter(
        initialLocation: '/places/p-wb-1',
        routes: [
          GoRoute(
            path: '/places/:id',
            builder: (_, s) => PlaceDetailScreen(placeId: s.pathParameters['id']!),
          ),
          GoRoute(
            path: '/ai',
            builder: (ctx, _) => Consumer(
              builder: (_, ref, __) => Scaffold(
                body: Text('WANDY_PROMPT:${ref.watch(pendingChatPromptProvider) ?? ""}'),
              ),
            ),
          ),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            placeDetailProvider('p-wb-1').overrideWith((_) async => _samplePlace()),
            locationServiceProvider.overrideWithValue(fakeLoc),
          ],
          child: Builder(builder: (ctx) {
            capturedContainer = ProviderScope.containerOf(ctx);
            return MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router);
          }),
        ),
      );
      await tester.pumpAndSettle();

      // GPS never auto-prompted on load.
      expect(fakeLoc.requestCalls, 0);

      await tester.tap(find.byKey(const Key('place_detail_ask_wandy')));
      await tester.pumpAndSettle();

      expect(
        capturedContainer.read(pendingChatPromptProvider),
        contains('Bảo tàng Chăm & Không gian Di sản Miền Trung'),
      );
      expect(find.textContaining('WANDY_PROMPT:'), findsOneWidget);
    });
  });

  group('Wave B — RecommendationScreen V2 & Responsive Grid', () {
    for (final spec in <(String, Size, double)>[
      ('phone-narrow', const Size(360, 800), 1.3),
      ('phone', const Size(390, 844), 1.0),
      ('desktop', const Size(1440, 900), 1.0),
    ]) {
      testWidgets('renders cleanly on ${spec.$1} (textScale ${spec.$3})',
          (tester) async {
        _setViewport(tester, spec.$2);
        final router = GoRouter(
          initialLocation: '/recommendations',
          routes: [
            GoRoute(
              path: '/recommendations',
              builder: (_, __) => MediaQuery(
                data: MediaQueryData(textScaler: TextScaler.linear(spec.$3)),
                child: const RecommendationScreen(),
              ),
            ),
            GoRoute(path: '/profile/preferences', builder: (_, __) => const Scaffold()),
          ],
        );

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              recommendationRepositoryProvider.overrideWithValue(
                _FakeRecoRepo((slug) => _sampleRecoResult(slug, coldStart: true)),
              ),
            ],
            child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.byType(AppStateBanner), findsOneWidget);
        expect(find.byKey(const Key('reco_item_p-1')), findsOneWidget);
        expect(find.byKey(const Key('reco_item_p-2')), findsOneWidget);
        expect(find.byIcon(Icons.star), findsNothing);

        if (spec.$2.width >= 1000) {
          final firstBox = tester.getTopLeft(find.byKey(const Key('reco_item_p-1')));
          final secondBox = tester.getTopLeft(find.byKey(const Key('reco_item_p-2')));
          // 2-column desktop row places both items side by side at the same top Y.
          expect(firstBox.dy, closeTo(secondBox.dy, 2.0));
          expect(secondBox.dx, greaterThan(firstBox.dx));
        }

        expect(tester.takeException(), isNull);
      });
    }
  });

  group('Wave B — Accented Vietnamese Copy & Layout (Auth + Trips @ 1.3x)', () {
    testWidgets('LoginScreen & RegisterScreen show GoMate V2 accented Vietnamese cleanly',
        (tester) async {
      _setViewport(tester, const Size(360, 800));
      await tester.pumpWidget(
        _scaledHost(
          textScale: 1.3,
          child: const LoginScreen(),
        ),
      );
      await tester.pump();
      expect(find.text('GoMate'), findsOneWidget);
      expect(find.text('Khám phá Việt Nam cùng AI'), findsOneWidget);
      expect(find.text('Đăng nhập'), findsOneWidget);
      expect(find.text('WanderAI'), findsNothing);
      expect(find.text('Dang nhap'), findsNothing);
      expect(tester.takeException(), isNull);

      await tester.pumpWidget(
        _scaledHost(
          textScale: 1.3,
          child: const RegisterScreen(),
        ),
      );
      await tester.pump();
      expect(find.text('Tạo tài khoản'), findsOneWidget);
      expect(find.text('Họ và tên'), findsOneWidget);
      expect(find.text('Đăng ký'), findsOneWidget);
      expect(find.text('Dang ky'), findsNothing);
      expect(tester.takeException(), isNull);
    });

    testWidgets('TripListScreen & TripDetailScreen accented copy and 360x800 @ 1.3x overflow free',
        (tester) async {
      _setViewport(tester, const Size(360, 800));
      const sampleTrip = TripModel(
        id: 'trip-1',
        userId: 'u1',
        title: 'Hành trình Miền Trung 4 ngày 3 đêm',
        description: 'Tham quan Hội An và Đà Nẵng',
        totalBudget: 6500000,
        currency: 'VND',
        travelStyle: 'COMFORT',
        status: 'PLANNED',
        interests: ['culture_history', 'food_cuisine'],
        itineraries: [
          ItineraryModel(
            id: 'day-1',
            tripId: 'trip-1',
            dayNumber: 1,
            title: 'Ngày 1: Phố cổ',
            items: [
              ItineraryItemModel(
                id: 'item-1',
                itineraryId: 'day-1',
                orderIndex: 1,
                activity: 'Tham quan Bảo tàng Chăm & dạo cầu Rồng',
                startTime: '09:00',
                estimatedCost: 120000,
                notes: 'Mang theo nón',
              ),
            ],
          ),
        ],
      );

      final repo = _FakeTripRepo(trips: [sampleTrip], detail: sampleTrip);

      await tester.pumpWidget(
        _scaledHost(
          textScale: 1.3,
          overrides: [tripRepositoryProvider.overrideWithValue(repo)],
          child: const TripListScreen(),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Chuyến đi của tôi'), findsOneWidget);
      expect(find.text('Đã lên lịch'), findsOneWidget);
      expect(find.text('Chuyen di cua toi'), findsNothing);
      expect(tester.takeException(), isNull);

      await tester.pumpWidget(
        _scaledHost(
          textScale: 1.3,
          overrides: [tripRepositoryProvider.overrideWithValue(repo)],
          child: const TripDetailScreen(tripId: 'trip-1'),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Ngân sách'), findsOneWidget);
      expect(find.text('Thời gian'), findsOneWidget);
      expect(find.text('Trợ lý Wandy AI'), findsOneWidget);
      await tester.drag(find.byType(CustomScrollView), const Offset(0, -400));
      await tester.pumpAndSettle();
      expect(find.text('Lịch trình chi tiết'), findsOneWidget);
      expect(find.text('Ngan sach'), findsNothing);
      expect(tester.takeException(), isNull);
    });
  });
}
