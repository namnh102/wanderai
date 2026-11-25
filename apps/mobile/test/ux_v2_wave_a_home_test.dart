import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/core/widgets/widgets.dart';
import 'package:wanderai_mobile/features/ai_chat/providers/chat_provider.dart';
import 'package:wanderai_mobile/features/home/presentation/home_screen.dart';
import 'package:wanderai_mobile/features/location/providers/user_location_provider.dart';

class _MockHomeAdapter implements HttpClientAdapter {
  final bool offlineOnDestinations;
  final bool emptyDestinations;
  final bool failPlaces;
  final Map<String, List<String>> requestedPaths = {'all': []};

  _MockHomeAdapter({
    this.offlineOnDestinations = false,
    this.emptyDestinations = false,
    this.failPlaces = false,
  });

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requestedPaths['all']!.add(options.path);
    if (options.path == '/destinations') {
      if (offlineOnDestinations) {
        throw DioException(
          requestOptions: options,
          type: DioExceptionType.connectionError,
          message: 'SocketException: Network is unreachable',
        );
      }
      if (emptyDestinations) {
        return _json({'success': true, 'data': {'items': []}});
      }
      return _json({
        'success': true,
        'data': {
          'items': [
            {
              'id': 'd-dn',
              'name': 'Đà Nẵng',
              'slug': 'da-nang',
              'province': 'Đà Nẵng',
              'region': 'central',
              'description': 'Thành phố biển miền Trung.',
              'rating': null,
              'reviewCount': 0,
              'isPopular': true,
              '_count': {'places': 123},
            },
            {
              'id': 'd-hn',
              'name': 'Hà Nội',
              'slug': 'ha-noi',
              'province': 'Hà Nội',
              'region': 'north',
              'description': 'Thủ đô nghìn năm văn hiến.',
              'rating': 4.8,
              'reviewCount': 12,
              'isPopular': true,
              '_count': {'places': 110},
            },
            {
              'id': 'd-sg',
              'name': 'TP. Hồ Chí Minh',
              'slug': 'ho-chi-minh',
              'province': 'TP. Hồ Chí Minh',
              'region': 'south',
              'description': 'Đô thị năng động miền Nam.',
              'rating': null,
              'reviewCount': 0,
              'isPopular': false,
              '_count': {'places': 2},
            },
          ],
        },
      });
    }

    if (options.path == '/places') {
      if (failPlaces) {
        throw DioException(
          requestOptions: options,
          type: DioExceptionType.connectionError,
        );
      }
      if (emptyDestinations) {
        return _json({'success': true, 'data': {'items': []}});
      }
      final search = options.queryParameters['search']?.toString() ?? '';
      final items = [
        {
          'id': 'p-1',
          'name': 'Bảo tàng Lịch sử Quốc gia',
          'address': '216 Trần Quang Khải, Hoàn Kiếm, Hà Nội',
          'latitude': 21.0245,
          'longitude': 105.8598,
          'rating': null,
          'reviewCount': 0,
          'category': {'name': 'museum'},
          'destination': {'name': 'Hà Nội'},
          'isVerified': true,
          'provenanceCount': 1,
        },
        {
          'id': 'p-2',
          'name': '324Coffee',
          'address': null,
          'latitude': 16.05699,
          'longitude': 108.21281,
          'rating': null,
          'reviewCount': 0,
          'category': {'name': 'cafe'},
          'destination': {'name': 'Đà Nẵng'},
          'isVerified': true,
          'provenanceCount': 1,
        },
      ];
      final filtered = search.isEmpty
          ? items
          : items
              .where((e) =>
                  (e['name'] as String).toLowerCase().contains(search.toLowerCase()))
              .toList();
      return _json({'success': true, 'data': {'items': filtered}});
    }

    if (options.path == '/places/nearby') {
      return _json({
        'success': true,
        'data': [
          {
            'id': 'p-near',
            'name': 'Tượng đài Lý Thái Tổ',
            'address': 'Đinh Tiên Hoàng, Hoàn Kiếm, Hà Nội',
            'latitude': 21.0285,
            'longitude': 105.8542,
            'rating': null,
            'reviewCount': 0,
            'distanceKm': 0.25,
            'category': {'name': 'culture'},
            'destination': {'name': 'Hà Nội'},
            'isVerified': true,
            'provenanceCount': 1,
          },
        ],
      });
    }

    if (options.path == '/users/me') {
      return _json({
        'success': true,
        'data': {
          'id': 'u-1',
          'email': 'minhanh@gomate.vn',
          'profile': {'displayName': 'Minh Anh'},
          'preferences': {
            'interests': ['food_cuisine', 'culture_history'],
          },
        },
      });
    }

    return _json({'success': true, 'data': {}});
  }

  ResponseBody _json(Map<String, dynamic> payload) {
    return ResponseBody.fromString(
      jsonEncode(payload),
      200,
      headers: {
        Headers.contentTypeHeader: ['application/json']
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _FakeGrantedLocationService implements LocationService {
  @override
  Future<LocationPermissionState> checkPermission() async =>
      LocationPermissionState.denied;

  @override
  Future<LocationPermissionState> requestPermission() async =>
      LocationPermissionState.granted;

  @override
  Future<bool> isServiceEnabled() async => true;

  @override
  Future<LocationFix> currentFix() async => LocationFix(
        position: const LatLng(21.0285, 105.8542),
        accuracyMeters: 15.0,
        timestamp: DateTime(2026, 11, 21, 10, 0),
      );

  @override
  Future<LatLng> currentPosition() async => const LatLng(21.0285, 105.8542);

  @override
  Future<bool> openAppSettings() async => true;

  @override
  Future<bool> openLocationSettings() async => true;
}

void main() {
  group('UX V2 Wave A — Theme & Shared Widgets', () {
    test('V2 editorial color and typography tokens exist cleanly', () {
      expect(AppColors.primaryDeep, const Color(0xFF123B43));
      expect(AppColors.warmBackground, const Color(0xFFF7F9F6));
      expect(AppColors.accentCoral, const Color(0xFFF07B5A));
      expect(AppColors.softBorder, const Color(0xFFE2E9E6));
      expect(AppTypography.eyebrow.fontSize, 11);
      expect(AppTheme.lightTheme.appBarTheme.backgroundColor, AppColors.surface);
    });

    testWidgets('Shared V2 widgets render without errors', (tester) async {
      bool tapped = false;
      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: Column(
              children: [
                AppSectionHeader(
                  title: 'Điểm đến nổi bật',
                  countLabel: '3 điểm đến',
                  actionLabel: 'Xem tất cả',
                  onAction: () => tapped = true,
                ),
                AppSearchBar(
                  readOnly: true,
                  onTap: () => tapped = true,
                ),
                AppStateBanner(
                  message: 'Mất kết nối',
                  tone: AppStateBannerTone.warning,
                  actionLabel: 'Thử lại',
                  onAction: () => tapped = true,
                ),
                const AppSkeletonBox(height: 24),
              ],
            ),
          ),
        ),
      );
      expect(find.text('Điểm đến nổi bật'), findsOneWidget);
      expect(find.text('Mất kết nối'), findsOneWidget);
      await tester.tap(find.text('Xem tất cả'));
      expect(tapped, isTrue);
    });
  });

  group('UX V2 Wave A — Home / Discover Vertical Slice', () {
    Dio buildDio(_MockHomeAdapter adapter) {
      final dio = Dio(BaseOptions(baseUrl: 'http://localhost'));
      dio.httpClientAdapter = adapter;
      return dio;
    }

    testWidgets('Renders real greeting, destinations, region filter & honest place cards',
        (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.reset());

      final dio = buildDio(_MockHomeAdapter());
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiClientProvider.overrideWithValue(dio),
            locationServiceProvider.overrideWithValue(_FakeGrantedLocationService()),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const HomeScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.text('Xin chào, Minh Anh 👋'), findsOneWidget);
      expect(find.byKey(const Key('home_recommendation_entry')), findsOneWidget);
      expect(find.text('Theo sở thích của bạn: Ẩm thực & Đặc sản, Văn hóa & Lịch sử'), findsOneWidget);
      expect(find.byKey(const Key('home_dest_da-nang')), findsOneWidget);
      expect(find.text('123 địa điểm'), findsOneWidget);
      expect(find.text('Chưa có đánh giá'), findsWidgets);

      await tester.scrollUntilVisible(
        find.text('Bảo tàng Lịch sử Quốc gia'),
        250,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.pump();
      expect(find.text('Bảo tàng Lịch sử Quốc gia'), findsOneWidget);

      // Scroll back and filter by Miền Nam
      await tester.drag(find.byType(CustomScrollView), const Offset(0, 700));
      await tester.pump();
      await tester.tap(find.byKey(const Key('home_region_south')));
      await tester.pump();
      expect(find.byKey(const Key('home_dest_ho-chi-minh')), findsOneWidget);
      expect(find.byKey(const Key('home_dest_da-nang')), findsNothing);
    });

    testWidgets('Explicit location button triggers PostGIS nearby places without auto-prompting',
        (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.reset());

      final dio = buildDio(_MockHomeAdapter());
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiClientProvider.overrideWithValue(dio),
            locationServiceProvider.overrideWithValue(_FakeGrantedLocationService()),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const HomeScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      await tester.drag(find.byType(CustomScrollView), const Offset(0, -520));
      await tester.pump();
      await tester.ensureVisible(find.text('Bật vị trí'));
      await tester.pump();
      expect(find.text('Bật vị trí'), findsOneWidget);
      expect(find.text('Tượng đài Lý Thái Tổ'), findsNothing);

      await tester.tap(find.text('Bật vị trí'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.text('Địa điểm gần bạn'), findsOneWidget);
      expect(find.text('Tượng đài Lý Thái Tổ'), findsOneWidget);
      expect(find.text('250m'), findsOneWidget);
    });

    testWidgets('Destination card opens DestinationPlacesSheet with real verified places',
        (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() => tester.view.reset());

      final dio = buildDio(_MockHomeAdapter());
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiClientProvider.overrideWithValue(dio),
            locationServiceProvider.overrideWithValue(_FakeGrantedLocationService()),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const HomeScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      await tester.drag(find.byType(CustomScrollView), const Offset(0, -180));
      await tester.pump();
      await tester.tap(find.byKey(const Key('home_dest_da-nang')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('Mở trên Bản đồ'), findsOneWidget);
      expect(find.text('324Coffee'), findsWidgets);
    });

    testWidgets('Wandy quick chip navigates cleanly and sets pending prompt',
        (tester) async {
      final dio = buildDio(_MockHomeAdapter());
      final router = GoRouter(
        initialLocation: '/',
        routes: [
          GoRoute(path: '/', builder: (_, __) => const HomeScreen()),
          GoRoute(path: '/ai', builder: (_, __) => const Scaffold(body: Text('WANDY_SCREEN'))),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiClientProvider.overrideWithValue(dio),
            locationServiceProvider.overrideWithValue(_FakeGrantedLocationService()),
          ],
          child: MaterialApp.router(
            theme: AppTheme.lightTheme,
            routerConfig: router,
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      await tester.tap(find.text('✦ Lịch trình Đà Nẵng 3N2Đ'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));

      expect(find.text('WANDY_SCREEN'), findsOneWidget);
      final container = ProviderScope.containerOf(tester.element(find.text('WANDY_SCREEN')));
      expect(container.read(pendingChatPromptProvider), contains('Đà Nẵng 3 ngày 2 đêm'));
    });

    testWidgets('Offline and empty states render honestly with retry action',
        (tester) async {
      // Offline state
      final offlineDio = buildDio(_MockHomeAdapter(offlineOnDestinations: true));
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiClientProvider.overrideWithValue(offlineDio),
            locationServiceProvider.overrideWithValue(_FakeGrantedLocationService()),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const HomeScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text('Không có kết nối mạng'), findsOneWidget);
      expect(find.text('Thử lại'), findsOneWidget);

      // Empty state
      final emptyDio = buildDio(_MockHomeAdapter(emptyDestinations: true));
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiClientProvider.overrideWithValue(emptyDio),
            locationServiceProvider.overrideWithValue(_FakeGrantedLocationService()),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const HomeScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text('Chưa có điểm đến'), findsOneWidget);
      // Partial error state: destinations loaded, places failed -> warning banner shown
      final partialDio = buildDio(_MockHomeAdapter(failPlaces: true));
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            apiClientProvider.overrideWithValue(partialDio),
            locationServiceProvider.overrideWithValue(_FakeGrantedLocationService()),
          ],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const HomeScreen(),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(
        find.text('Kết nối không ổn định, chưa tải được địa điểm xác minh.'),
        findsOneWidget,
      );
    });

    testWidgets('Zero RenderFlex overflow across 360px, 390px, 430px, 1440px and 1.3x text scale',
        (tester) async {
      const sizes = [
        Size(360, 800),
        Size(390, 844),
        Size(430, 932),
        Size(1440, 900),
      ];

      for (final size in sizes) {
        tester.view.physicalSize = size;
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() => tester.view.reset());

        final dio = buildDio(_MockHomeAdapter());
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              apiClientProvider.overrideWithValue(dio),
              locationServiceProvider.overrideWithValue(_FakeGrantedLocationService()),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              home: const MediaQuery(
                data: MediaQueryData(textScaler: TextScaler.linear(1.3)),
                child: HomeScreen(),
              ),
            ),
          ),
        );
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 50));
        expect(tester.takeException(), isNull, reason: 'Initial layout overflow on size $size');

        await tester.drag(find.byType(CustomScrollView), const Offset(0, -360));
        await tester.pump();
        expect(tester.takeException(), isNull, reason: 'Scrolled layout overflow on size $size');
      }
    });
  });
}
