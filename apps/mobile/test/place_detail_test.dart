import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/core/widgets/widgets.dart';
import 'package:wanderai_mobile/features/auth/data/auth_repository.dart';
import 'package:wanderai_mobile/features/auth/providers/auth_provider.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/map/data/place_repository.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/place_preview_sheet.dart';
import 'package:wanderai_mobile/features/map/providers/map_provider.dart';
import 'package:wanderai_mobile/features/places/data/navigation_service.dart';
import 'package:wanderai_mobile/features/places/data/review_repository.dart';
import 'package:wanderai_mobile/features/places/presentation/place_detail_screen.dart';

class _FakeRepo implements PlaceRepository {
  final Future<PlaceModel> Function(String id) onGet;
  _FakeRepo(this.onGet);

  @override
  Future<PlaceModel> getPlaceById(String id) => onGet(id);

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeAuthRepo extends AuthRepository {
  _FakeAuthRepo() : super(Dio());

  @override
  Future<bool> restoreSession() async => true;
}

class _FakeReviewRepo extends ReviewRepository {
  final Future<PlaceReviewModel> Function({
    required String placeId,
    required double rating,
    required String content,
  }) onCreate;

  _FakeReviewRepo(this.onCreate) : super(Dio());

  @override
  Future<PlaceReviewModel> createReview({
    required String placeId,
    required double rating,
    required String content,
  }) =>
      onCreate(placeId: placeId, rating: rating, content: content);
}

const _verifiedJson = <String, dynamic>{
  'id': 'p1',
  'name': 'Chùa Trấn Quốc',
  'nameEn': 'Tran Quoc Pagoda',
  'description': null,
  'address': '46 Thanh Niên, Tây Hồ, Hà Nội',
  'latitude': 21.0485,
  'longitude': 105.8363,
  'rating': null,
  'reviewCount': 0,
  'category': {'name': 'culture'},
  'destination': {'name': 'Hà Nội'},
  'isVerified': true,
  'provenanceCount': 1,
  'openingHours': 'Mo-Su 08:00-17:00',
  'website': 'https://example.org/tran-quoc',
  'phone': '+84 24 1234 5678',
  'source': {
    'name': 'OpenStreetMap',
    'sourceId': 'way/123',
    'canonicalUrl': 'https://www.openstreetmap.org/way/123',
    'license': 'ODbL 1.0',
    'attribution': '© OpenStreetMap contributors',
  },
};

const _unverifiedJson = <String, dynamic>{
  'id': 'p2',
  'name': 'Địa điểm thử',
  'latitude': 16.06,
  'longitude': 108.22,
  'rating': null,
  'category': {'name': 'cafe'},
  'isVerified': false,
  'provenanceCount': 0,
  'address': null,
  'openingHours': null,
  'website': null,
  'phone': null,
  'source': null,
};

Widget _app(Widget home, {List<Override> overrides = const []}) {
  return ProviderScope(
    overrides: overrides,
    child: MaterialApp(theme: AppTheme.lightTheme, home: home),
  );
}

Widget _screenApp(Future<PlaceModel> Function(String) onGet, String id) {
  return _app(
    PlaceDetailScreen(placeId: id),
    overrides: [placeRepositoryProvider.overrideWithValue(_FakeRepo(onGet))],
  );
}

void main() {
  group('PlaceModel detail parsing', () {
    test('parses opening hours, contact and OSM source', () {
      final p = PlaceModel.fromJson(Map<String, dynamic>.from(_verifiedJson));
      expect(p.isVerified, isTrue);
      expect(p.openingHours, 'Mo-Su 08:00-17:00');
      expect(p.website, 'https://example.org/tran-quoc');
      expect(p.phone, '+84 24 1234 5678');
      expect(p.source!.name, 'OpenStreetMap');
      expect(p.source!.canonicalUrl, 'https://www.openstreetmap.org/way/123');
      expect(p.source!.license, 'ODbL 1.0');
      expect(p.categoryName, 'culture');
      expect(p.destinationName, 'Hà Nội');
    });

    test('null rating stays null and missing optional fields are null', () {
      final p = PlaceModel.fromJson(Map<String, dynamic>.from(_unverifiedJson));
      expect(p.rating, isNull);
      expect(p.openingHours, isNull);
      expect(p.website, isNull);
      expect(p.phone, isNull);
      expect(p.source, isNull);
      expect(p.isVerified, isFalse);
    });

    test('blank strings are treated as unavailable', () {
      final p = PlaceModel.fromJson({
        'id': 'x',
        'name': 'X',
        'openingHours': '   ',
        'website': '',
        'phone': ' ',
      });
      expect(p.openingHours, isNull);
      expect(p.website, isNull);
      expect(p.phone, isNull);
    });

    test('list responses without detail fields still parse (backward compatible)', () {
      final p = PlaceModel.fromJson({'id': 'x', 'name': 'X', 'isVerified': true});
      expect(p.source, isNull);
      expect(p.isVerified, isTrue);
    });
  });

  group('PlaceDetailScreen states', () {
    testWidgets('shows loading state while fetching', (tester) async {
      final c = Completer<PlaceModel>();
      await tester.pumpWidget(_screenApp((_) => c.future, 'p1'));
      await tester.pump();
      expect(find.byType(AppLoading), findsOneWidget);
      c.complete(PlaceModel.fromJson(Map<String, dynamic>.from(_verifiedJson)));
      await tester.pumpAndSettle();
      expect(find.byType(AppLoading), findsNothing);
    });

    testWidgets('shows retryable error state on failure', (tester) async {
      var calls = 0;
      await tester.pumpWidget(_screenApp((_) async {
        calls++;
        throw Exception('network down');
      }, 'p1'));
      await tester.pumpAndSettle();
      expect(find.byType(AppErrorState), findsOneWidget);
      expect(find.text('Thử lại'), findsOneWidget);
      await tester.tap(find.text('Thử lại'));
      await tester.pumpAndSettle();
      expect(calls, 2);
    });

    testWidgets('404 shows empty "not found" state', (tester) async {
      await tester.pumpWidget(_screenApp((_) async {
        throw DioException(
          requestOptions: RequestOptions(path: '/places/x'),
          response: Response(
              requestOptions: RequestOptions(path: '/places/x'), statusCode: 404),
        );
      }, 'x'));
      await tester.pumpAndSettle();
      expect(find.byType(AppEmptyState), findsOneWidget);
      expect(find.text('Không tìm thấy địa điểm'), findsOneWidget);
    });
  });

  group('PlaceDetailScreen content', () {
    testWidgets('verified place: badge, hours, contact, OSM source, CTA', (tester) async {
      await tester.pumpWidget(_screenApp(
        (_) async => PlaceModel.fromJson(Map<String, dynamic>.from(_verifiedJson)),
        'p1',
      ));
      await tester.pumpAndSettle();

      expect(find.text('Chùa Trấn Quốc'), findsOneWidget);
      expect(find.text('Văn hóa'), findsOneWidget);
      expect(find.text('Hà Nội'), findsOneWidget);
      expect(find.text('Đã xác minh'), findsOneWidget);
      expect(find.text('Chưa có đánh giá'), findsOneWidget);
      expect(find.text('46 Thanh Niên, Tây Hồ, Hà Nội'), findsOneWidget);
      expect(find.text('Mo-Su 08:00-17:00'), findsOneWidget);
      expect(find.text('Chưa có thông tin giờ mở cửa.'), findsNothing);
      expect(find.text('https://example.org/tran-quoc'), findsOneWidget);
      expect(find.text('+84 24 1234 5678'), findsOneWidget);
      expect(find.text('Nguồn: OpenStreetMap'), findsOneWidget);
      expect(find.text('https://www.openstreetmap.org/way/123'), findsOneWidget);
      expect(find.byKey(const Key('place_detail_coordinates')), findsOneWidget);
      expect(find.text('Chỉ đường'), findsOneWidget);
    });

    testWidgets('unverified place: no verified badge, honest unavailable states', (tester) async {
      await tester.pumpWidget(_screenApp(
        (_) async => PlaceModel.fromJson(Map<String, dynamic>.from(_unverifiedJson)),
        'p2',
      ));
      await tester.pumpAndSettle();

      expect(find.text('Đã xác minh'), findsNothing);
      expect(find.text('Chưa có đánh giá'), findsOneWidget);
      expect(find.text('Chưa có thông tin giờ mở cửa.'), findsOneWidget);
      expect(find.text('Chưa có thông tin địa chỉ.'), findsOneWidget);
      expect(find.text('Địa điểm này chưa được xác minh nguồn dữ liệu.'), findsOneWidget);
      expect(find.text('Nguồn: OpenStreetMap'), findsNothing);
      expect(find.byKey(const Key('place_detail_website')), findsNothing);
      expect(find.byKey(const Key('place_detail_phone')), findsNothing);
      expect(find.text('Liên hệ'), findsNothing);
    });

    testWidgets('real rating is displayed when available', (tester) async {
      final json = Map<String, dynamic>.from(_verifiedJson)
        ..['rating'] = 4.2
        ..['reviewCount'] = 7;
      await tester.pumpWidget(_screenApp((_) async => PlaceModel.fromJson(json), 'p1'));
      await tester.pumpAndSettle();
      expect(find.text('4.2'), findsOneWidget);
      expect(find.text('Chưa có đánh giá'), findsNothing);
    });

    testWidgets('missing opening hours only: other facts still render', (tester) async {
      final json = Map<String, dynamic>.from(_verifiedJson)..['openingHours'] = null;
      await tester.pumpWidget(_screenApp((_) async => PlaceModel.fromJson(json), 'p1'));
      await tester.pumpAndSettle();
      expect(find.text('Chưa có thông tin giờ mở cửa.'), findsOneWidget);
      expect(find.text('Đã xác minh'), findsOneWidget);
    });

    testWidgets('source URL, website and directions invoke their handlers', (tester) async {
      final opened = <String>[];
      var directions = 0;
      final place = PlaceModel.fromJson(Map<String, dynamic>.from(_verifiedJson));
      await tester.pumpWidget(_app(Scaffold(
        body: PlaceDetailView(
          place: place,
          onOpenUrl: opened.add,
          onDirections: () => directions++,
        ),
      )));
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.byKey(const Key('place_detail_source_url')));
      await tester.tap(find.byKey(const Key('place_detail_source_url')));
      await tester.ensureVisible(find.byKey(const Key('place_detail_website')));
      await tester.tap(find.byKey(const Key('place_detail_website')));
      await tester.tap(find.byKey(const Key('place_detail_directions')));
      expect(opened, [
        'https://www.openstreetmap.org/way/123',
        'https://example.org/tran-quoc',
      ]);
      expect(directions, 1);
    });

    test('directions never fall back to the openstreetmap.org website', () {
      for (final platform in NavPlatform.values) {
        final uris = directionsCandidates(
            destLat: 21.0485, destLng: 105.8363, platform: platform);
        expect(uris, isNotEmpty);
        for (final u in uris) {
          expect(u.host, isNot(contains('openstreetmap')));
        }
      }
    });
  });

  group('Preview sheet & navigation', () {
    testWidgets('preview sheet shows "Xem chi tiết" only when a handler is given', (tester) async {
      final place = PlaceModel.fromJson(Map<String, dynamic>.from(_verifiedJson));
      var taps = 0;
      await tester.pumpWidget(_app(Scaffold(
        body: PlacePreviewSheet(place: place, onClose: () {}, onViewDetail: () => taps++),
      )));
      expect(find.text('Xem chi tiết'), findsOneWidget);
      await tester.tap(find.byKey(const Key('place_preview_view_detail')));
      expect(taps, 1);

      await tester.pumpWidget(_app(Scaffold(
        body: PlacePreviewSheet(place: place, onClose: () {}),
      )));
      expect(find.text('Xem chi tiết'), findsNothing);
    });

    testWidgets('/places/:id pushes over the map and back returns to it', (tester) async {
      final router = GoRouter(
        initialLocation: '/map',
        routes: [
          GoRoute(
            path: '/map',
            builder: (c, _) => Scaffold(
              body: TextButton(
                onPressed: () => c.push('/places/p1'),
                child: const Text('MAP_SCREEN_OPEN'),
              ),
            ),
          ),
          GoRoute(
            path: '/places/:id',
            builder: (c, s) => PlaceDetailScreen(placeId: s.pathParameters['id']!),
          ),
        ],
      );
      await tester.pumpWidget(ProviderScope(
        overrides: [
          placeRepositoryProvider.overrideWithValue(_FakeRepo(
            (_) async => PlaceModel.fromJson(Map<String, dynamic>.from(_verifiedJson)),
          )),
        ],
        child: MaterialApp.router(theme: AppTheme.lightTheme, routerConfig: router),
      ));

      await tester.tap(find.text('MAP_SCREEN_OPEN'));
      await tester.pumpAndSettle();
      expect(find.text('Chùa Trấn Quốc'), findsOneWidget);

      await tester.tap(find.byKey(const Key('place_detail_back')));
      await tester.pumpAndSettle();
      expect(find.text('MAP_SCREEN_OPEN'), findsOneWidget);
      expect(find.text('Chùa Trấn Quốc'), findsNothing);
    });
  });

  group('Factual address consistency (preview = detail)', () {
    const fabricated = 'Chùa Trấn Quốc, hanoi';

    Future<void> pumpPreview(WidgetTester tester, PlaceModel p) async {
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(_app(Scaffold(body: PlacePreviewSheet(place: p, onClose: () {}))));
    }

    Future<void> pumpDetail(WidgetTester tester, PlaceModel p) async {
      await tester.pumpWidget(const SizedBox());
      await tester.pumpWidget(_screenApp((_) async => p, 'p1'));
      await tester.pumpAndSettle();
    }

    testWidgets('verified place with real address shows it in preview and detail', (tester) async {
      final json = Map<String, dynamic>.from(_verifiedJson)..['address'] = '46 Thanh Niên, Tây Hồ, Hà Nội';
      final place = PlaceModel.fromJson(json);
      expect(place.hasAddress, isTrue);
      await pumpPreview(tester, place);
      expect(find.byKey(const Key('place_preview_address')), findsOneWidget);
      expect(find.text('46 Thanh Niên, Tây Hồ, Hà Nội'), findsOneWidget);
      expect(find.text(PlaceModel.addressUnavailableText), findsNothing);

      await pumpDetail(tester, place);
      expect(find.text('46 Thanh Niên, Tây Hồ, Hà Nội'), findsOneWidget);
    });

    testWidgets('verified place with null address shows exact unavailable text', (tester) async {
      final json = Map<String, dynamic>.from(_verifiedJson)..['address'] = null;
      final place = PlaceModel.fromJson(json);
      expect(place.hasAddress, isFalse);
      expect(PlaceModel.addressUnavailableText, 'Chưa có thông tin địa chỉ.');
      await pumpPreview(tester, place);
      expect(find.text('Chưa có thông tin địa chỉ.'), findsOneWidget);

      await pumpDetail(tester, place);
      expect(find.text('Chưa có thông tin địa chỉ.'), findsOneWidget);
    });

    testWidgets('never fabricates "<name>, <city>" when address is null or blank', (tester) async {
      for (final addr in <String?>[null, '', '   ']) {
        final json = Map<String, dynamic>.from(_verifiedJson)
          ..['address'] = addr
          ..['destinationName'] = 'hanoi';
        final place = PlaceModel.fromJson(json);
        expect(place.addressDisplay, PlaceModel.addressUnavailableText);
        await pumpPreview(tester, place);
        expect(find.text(fabricated), findsNothing);
        await pumpDetail(tester, place);
        expect(find.text(fabricated), findsNothing);
      }
    });
  });

  group('GAP-14: Review sheet lifecycle & overflow hardening', () {
    testWidgets(
      'dismissing _openReviewSheet mid-request with failing createReview and keyboard open produces zero FlutterErrors',
      (tester) async {
        final errors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          errors.add(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        final completer = Completer<PlaceReviewModel>();
        final authNotifier = AuthNotifier(_FakeAuthRepo());

        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              authProvider.overrideWith((_) => authNotifier),
              placeRepositoryProvider.overrideWithValue(
                _FakeRepo(
                  (_) async => PlaceModel.fromJson(
                    Map<String, dynamic>.from(_verifiedJson),
                  ),
                ),
              ),
              reviewRepositoryProvider.overrideWithValue(
                _FakeReviewRepo(
                  ({required placeId, required rating, required content}) =>
                      completer.future,
                ),
              ),
            ],
            child: MaterialApp(
              theme: AppTheme.lightTheme,
              home: const MediaQuery(
                data: MediaQueryData(
                  size: Size(360, 640),
                  viewInsets: EdgeInsets.only(bottom: 300),
                ),
                child: PlaceDetailScreen(placeId: 'p1'),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();

        final writeReviewBtn =
            find.byKey(const Key('place_detail_write_review'));
        await tester.ensureVisible(writeReviewBtn);
        await tester.tap(writeReviewBtn);
        await tester.pumpAndSettle();

        final inputFinder = find.byKey(const Key('review_content_input'));
        expect(inputFinder, findsOneWidget);
        await tester.tap(inputFinder);
        await tester.enterText(inputFinder, 'Trải nghiệm tuyệt vời ở Hạ Long');
        await tester.pump();

        final submitFinder = find.byKey(const Key('review_submit_button'));
        await tester.ensureVisible(submitFinder);
        await tester.tap(submitFinder);
        await tester.pump();

        // Dismiss the bottom sheet mid-request while exit animation runs
        Navigator.of(tester.element(inputFinder)).pop();
        await tester.pump(const Duration(milliseconds: 50));

        // Fail the in-flight createReview after dismissal
        completer.completeError(
          DioException(
            requestOptions: RequestOptions(path: '/reviews'),
            type: DioExceptionType.connectionError,
          ),
        );
        await tester.pumpAndSettle();

        expect(errors, isEmpty);
      },
    );
  });
}
