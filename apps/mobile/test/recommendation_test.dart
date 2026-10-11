import 'dart:async';
import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:wanderai_mobile/features/recommendations/data/recommendation_models.dart';
import 'package:wanderai_mobile/features/recommendations/data/recommendation_repository.dart';
import 'package:wanderai_mobile/features/recommendations/presentation/recommendation_screen.dart';
import 'package:wanderai_mobile/features/recommendations/providers/recommendation_provider.dart';

/// Shape captured from a live `GET /places/recommendations?destination=da-nang`
/// (NestJS envelope around the REC-A FastAPI response).
Map<String, dynamic> envelope({
  String destinationSlug = 'da-nang',
  String destinationName = 'Đà Nẵng',
  bool cold = false,
  List<Map<String, dynamic>>? items,
}) {
  final recs = items ??
      [
        {
          'place_id': 'p-1',
          'name': 'Art in Paradise Da Nang 3D Museum',
          'destination': destinationName,
          'destination_slug': destinationSlug,
          'category': 'culture',
          'score': 0.707107,
          'rank': 1,
          'matched_interests': ['culture_history'],
          'explanation': {
            'reason_code': 'PREFERENCE_TAXONOMY_MATCH',
            'matched_interests': ['culture_history'],
            'matched_taxonomy': ['CULTURE_HERITAGE'],
            'text': 'Phù hợp vì bạn quan tâm đến văn hóa & lịch sử.',
          },
          'strategy': 'rec-a1_content_match',
        },
        {
          'place_id': 'p-2',
          'name': 'BaBaBa Japanese Restaurant',
          'destination': destinationName,
          'destination_slug': destinationSlug,
          'category': 'restaurant',
          'score': 0.707107,
          'rank': 2,
          'matched_interests': ['food_cuisine'],
          'explanation': {
            'reason_code': 'PREFERENCE_TAXONOMY_MATCH',
            'matched_interests': ['food_cuisine'],
            'matched_taxonomy': ['FOOD_BEVERAGE'],
            'text': 'Phù hợp vì bạn quan tâm đến ẩm thực & đặc sản.',
          },
          'strategy': 'rec-a1_content_match',
        },
      ];
  return {
    'success': true,
    'data': {
      'recommendations': recs,
      'metadata': {
        'algorithm': 'Cosine Content-Based Baseline',
        'model': 'rec-a1',
        'destination_filter': destinationSlug,
        'total_candidates': 289,
        'returned_count': recs.length,
        'cold_start': cold,
      },
      'unsupported_user_features': [
        {
          'feature': 'travelStyle',
          'status': 'AVAILABLE_USER_FEATURE_NOT_USED_IN_V1',
          'reason': 'No validated POI-side signal.',
        },
      ],
    },
    'timestamp': '2026-10-12T00:00:00.000Z',
  };
}

class CapturingAdapter implements HttpClientAdapter {
  RequestOptions? last;
  final Object? Function(RequestOptions) responder;
  final int status;
  CapturingAdapter(this.responder, {this.status = 200});

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<List<int>>? requestStream, Future<void>? cancelFuture) async {
    last = options;
    final body = responder(options);
    if (body is DioException) throw body;
    return ResponseBody.fromString(
      jsonEncode(body),
      status,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

RecommendationRepository repoWith(CapturingAdapter a) {
  final dio = Dio(BaseOptions(baseUrl: 'http://test'));
  dio.httpClientAdapter = a;
  return RecommendationRepository(dio);
}

class FakeRepo extends RecommendationRepository {
  final Future<RecommendationResult> Function(String destination) handler;
  final List<String> calls = [];
  FakeRepo(this.handler) : super(Dio());

  @override
  Future<RecommendationResult> fetch({
    required String destination,
    int topK = RecommendationRepository.defaultTopK,
    String model = RecommendationRepository.defaultModel,
  }) {
    calls.add(destination);
    return handler(destination);
  }
}

RecommendationResult result(String slug, {bool cold = false, bool empty = false}) =>
    RecommendationResult.fromJson(
      (envelope(
        destinationSlug: slug,
        cold: cold,
        items: empty ? <Map<String, dynamic>>[] : null,
      )['data']) as Map<String, dynamic>,
    );

void main() {
  group('Repository', () {
    test('parses the real response fixture', () async {
      final repo = repoWith(CapturingAdapter((_) => envelope()));
      final r = await repo.fetch(destination: 'da-nang');
      expect(r.recommendations, hasLength(2));
      final first = r.recommendations.first;
      expect(first.placeId, 'p-1');
      expect(first.destinationSlug, 'da-nang');
      expect(first.category, 'culture');
      expect(first.score, closeTo(0.707107, 1e-9));
      expect(first.rank, 1);
      expect(first.matchedInterests, ['culture_history']);
      expect(first.explanation.reasonCode, 'PREFERENCE_TAXONOMY_MATCH');
      expect(first.explanation.matchedTaxonomy, ['CULTURE_HERITAGE']);
      expect(first.explanation.text, contains('văn hóa'));
      expect(first.strategy, 'rec-a1_content_match');
      expect(r.metadata.model, 'rec-a1');
      expect(r.metadata.destinationFilter, 'da-nang');
      expect(r.metadata.totalCandidates, 289);
      expect(r.metadata.returnedCount, 2);
      expect(r.metadata.coldStart, isFalse);
      expect(r.unsupportedUserFeatures.single.feature, 'travelStyle');
    });

    test('sends destination, topK=10 and model=rec-a1 to NestJS (never FastAPI)', () async {
      final adapter = CapturingAdapter((_) => envelope());
      await repoWith(adapter).fetch(destination: 'ha-noi');
      final o = adapter.last!;
      expect(o.path, '/places/recommendations');
      expect(o.uri.host, 'test');
      expect(o.queryParameters, {'destination': 'ha-noi', 'topK': 10, 'model': 'rec-a1'});
    });

    Future<RecommendationException> failWith(int status, Object body) async {
      final repo = repoWith(CapturingAdapter((_) => body, status: status));
      try {
        await repo.fetch(destination: 'da-nang');
      } on RecommendationException catch (e) {
        return e;
      }
      fail('expected RecommendationException');
    }

    test('maps backend 400 string message safely', () async {
      final e = await failWith(400, {'success': false, 'statusCode': 400, 'message': 'topK phải là số nguyên từ 1 đến 50'});
      expect(e.message, 'topK phải là số nguyên từ 1 đến 50');
      expect(e.statusCode, 400);
    });

    test('never shows raw maps: object message becomes a generic readable text', () async {
      final e = await failWith(422, {'success': false, 'message': {'type': 'x', 'loc': ['body']}});
      expect(e.message, 'Yêu cầu gợi ý không hợp lệ.');
      expect(e.message, isNot(contains('{')));
    });

    test('maps 401 and 503 and connection errors', () async {
      expect((await failWith(401, {'message': 'Unauthorized'})).message, contains('đăng nhập lại'));
      expect((await failWith(503, {'message': 'AI Recommendation Service không phản hồi. Vui lòng thử lại sau.'})).message,
          contains('không phản hồi'));
      final repo = repoWith(CapturingAdapter((o) => DioException(requestOptions: o, type: DioExceptionType.connectionError)));
      try {
        await repo.fetch(destination: 'da-nang');
        fail('should throw');
      } on RecommendationException catch (e) {
        expect(e.message, 'Không có kết nối mạng.');
      }
    });
  });

  group('Provider state', () {
    ProviderContainer containerFor(FakeRepo repo) {
      final c = ProviderContainer(overrides: [recommendationRepositoryProvider.overrideWithValue(repo)]);
      addTearDown(c.dispose);
      return c;
    }

    test('loading -> success', () async {
      final completer = Completer<RecommendationResult>();
      final c = containerFor(FakeRepo((_) => completer.future));
      final f = c.read(recommendationProvider.notifier).load();
      expect(c.read(recommendationProvider).status, RecommendationStatus.loading);
      completer.complete(result('da-nang'));
      await f;
      final s = c.read(recommendationProvider);
      expect(s.status, RecommendationStatus.success);
      expect(s.result!.recommendations, hasLength(2));
    });

    test('loading -> empty', () async {
      final c = containerFor(FakeRepo((_) async => result('da-nang', empty: true)));
      await c.read(recommendationProvider.notifier).load();
      expect(c.read(recommendationProvider).status, RecommendationStatus.empty);
    });

    test('loading -> error with readable message, then retry succeeds', () async {
      var fail = true;
      final c = containerFor(FakeRepo((_) async {
        if (fail) throw const RecommendationException('Không có kết nối mạng.');
        return result('da-nang');
      }));
      final n = c.read(recommendationProvider.notifier);
      await n.load();
      expect(c.read(recommendationProvider).status, RecommendationStatus.error);
      expect(c.read(recommendationProvider).errorMessage, 'Không có kết nối mạng.');
      fail = false;
      await n.retry();
      expect(c.read(recommendationProvider).status, RecommendationStatus.success);
    });

    test('cold-start is a valid success, not an error', () async {
      final c = containerFor(FakeRepo((_) async => result('da-nang', cold: true)));
      await c.read(recommendationProvider.notifier).load();
      final s = c.read(recommendationProvider);
      expect(s.status, RecommendationStatus.success);
      expect(s.result!.metadata.coldStart, isTrue);
    });

    test('destination switch clears the old result and ignores a late stale response', () async {
      final completers = <String, Completer<RecommendationResult>>{
        'da-nang': Completer(),
        'ha-noi': Completer(),
      };
      final repo = FakeRepo((d) => completers[d]!.future);
      final c = containerFor(repo);
      final n = c.read(recommendationProvider.notifier);

      final first = n.selectDestination(RecommendationDestination.daNang);
      final second = n.selectDestination(RecommendationDestination.haNoi);
      final mid = c.read(recommendationProvider);
      expect(mid.destination, RecommendationDestination.haNoi);
      expect(mid.result, isNull); // nothing from another destination while loading

      completers['ha-noi']!.complete(result('ha-noi'));
      await second;
      completers['da-nang']!.complete(result('da-nang')); // late, stale
      await first;

      final s = c.read(recommendationProvider);
      expect(s.destination, RecommendationDestination.haNoi);
      expect(s.result!.metadata.destinationFilter, 'ha-noi');
      expect(s.result!.recommendations.every((r) => r.destinationSlug == 'ha-noi'), isTrue);
      expect(repo.calls, ['da-nang', 'ha-noi']);
    });
  });

  group('Recommendation screen', () {
    Widget app(FakeRepo repo) {
      final router = GoRouter(
        initialLocation: '/recommendations',
        routes: [
          GoRoute(path: '/recommendations', builder: (_, __) => const RecommendationScreen()),
          GoRoute(
            path: '/places/:id',
            builder: (_, s) => Scaffold(body: Text('PLACE DETAIL ${s.pathParameters['id']}')),
          ),
          GoRoute(path: '/profile/preferences', builder: (_, __) => const Scaffold(body: Text('PREFS'))),
        ],
      );
      return ProviderScope(
        overrides: [recommendationRepositoryProvider.overrideWithValue(repo)],
        child: MaterialApp.router(routerConfig: router),
      );
    }

    void bigView(WidgetTester tester) {
      tester.view.physicalSize = const Size(800, 1600);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });
    }

    testWidgets('destination selector offers exactly Hà Nội, Đà Nẵng, Hạ Long (no free text)', (tester) async {
      bigView(tester);
      await tester.pumpWidget(app(FakeRepo((d) async => result(d))));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('reco_destination_ha-noi')), findsOneWidget);
      expect(find.byKey(const Key('reco_destination_da-nang')), findsOneWidget);
      expect(find.byKey(const Key('reco_destination_ha-long')), findsOneWidget);
      expect(find.text('Hà Nội'), findsOneWidget);
      expect(find.text('Đà Nẵng'), findsOneWidget);
      expect(find.text('Hạ Long'), findsOneWidget);
      expect(find.byType(TextField), findsNothing);
    });

    testWidgets('renders list, category, explanation text, matched interests and no rating', (tester) async {
      bigView(tester);
      await tester.pumpWidget(app(FakeRepo((d) async => result(d))));
      await tester.pumpAndSettle();
      expect(find.text('Art in Paradise Da Nang 3D Museum'), findsOneWidget);
      expect(find.text('BaBaBa Japanese Restaurant'), findsOneWidget);
      expect(find.text('Văn hóa'), findsOneWidget); // category label
      expect(find.text('Nhà hàng'), findsOneWidget);
      expect(find.text('Phù hợp vì bạn quan tâm đến văn hóa & lịch sử.'), findsOneWidget);
      expect(find.text('Văn hóa & Lịch sử'), findsOneWidget); // matched interest chip
      expect(find.text('Ẩm thực & Đặc sản'), findsOneWidget);
      expect(find.byIcon(Icons.star), findsNothing);
      expect(find.byIcon(Icons.star_rounded), findsNothing);
      expect(find.textContaining('★'), findsNothing);
      expect(find.byKey(const Key('reco_cold_start_notice')), findsNothing);
    });

    testWidgets('cold start shows the list plus an informational notice', (tester) async {
      bigView(tester);
      await tester.pumpWidget(app(FakeRepo((d) async => result(d, cold: true))));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('reco_cold_start_notice')), findsOneWidget);
      expect(find.text('Art in Paradise Da Nang 3D Museum'), findsOneWidget);
    });

    testWidgets('loading state is shown while the request is pending', (tester) async {
      bigView(tester);
      final c = Completer<RecommendationResult>();
      await tester.pumpWidget(app(FakeRepo((_) => c.future)));
      await tester.pump();
      await tester.pump();
      expect(find.text('Đang tìm gợi ý phù hợp...'), findsOneWidget);
      c.complete(result('da-nang'));
      await tester.pumpAndSettle();
      expect(find.text('Đang tìm gợi ý phù hợp...'), findsNothing);
    });

    testWidgets('empty state', (tester) async {
      bigView(tester);
      await tester.pumpWidget(app(FakeRepo((d) async => result(d, empty: true))));
      await tester.pumpAndSettle();
      expect(find.text('Chưa có gợi ý'), findsOneWidget);
      expect(find.text('Cập nhật sở thích'), findsOneWidget);
    });

    testWidgets('error state shows readable message and retry recovers', (tester) async {
      bigView(tester);
      var failing = true;
      await tester.pumpWidget(app(FakeRepo((d) async {
        if (failing) throw const RecommendationException('Không có kết nối mạng.');
        return result(d);
      })));
      await tester.pumpAndSettle();
      expect(find.text('Không có kết nối mạng.'), findsOneWidget);
      failing = false;
      await tester.tap(find.text('Thử lại'));
      await tester.pumpAndSettle();
      expect(find.text('Art in Paradise Da Nang 3D Museum'), findsOneWidget);
    });

    testWidgets('switching destination refetches and never shows the previous destination items', (tester) async {
      bigView(tester);
      final repo = FakeRepo((d) async => RecommendationResult.fromJson((envelope(
            destinationSlug: d,
            items: [
              {
                'place_id': 'id-$d',
                'name': 'Place of $d',
                'destination': d,
                'destination_slug': d,
                'category': 'attraction',
                'score': 0.5,
                'rank': 1,
                'matched_interests': <String>[],
                'explanation': {'reason_code': 'X', 'matched_interests': <String>[], 'matched_taxonomy': <String>[], 'text': 'Lý do $d'},
                'strategy': 's',
              }
            ],
          )['data']) as Map<String, dynamic>));
      await tester.pumpWidget(app(repo));
      await tester.pumpAndSettle();
      expect(find.text('Place of da-nang'), findsOneWidget);
      await tester.tap(find.byKey(const Key('reco_destination_ha-long')));
      await tester.pumpAndSettle();
      expect(find.text('Place of ha-long'), findsOneWidget);
      expect(find.text('Place of da-nang'), findsNothing);
      expect(repo.calls, ['da-nang', 'ha-long']);
    });

    testWidgets('tapping a result opens Place Detail by place_id', (tester) async {
      bigView(tester);
      await tester.pumpWidget(app(FakeRepo((d) async => result(d))));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('reco_item_p-2')));
      await tester.pumpAndSettle();
      expect(find.text('PLACE DETAIL p-2'), findsOneWidget);
    });
  });
}
