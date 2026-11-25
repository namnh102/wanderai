import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:wanderai_mobile/core/network/api_client.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/core/widgets/app_state_banner.dart';
import 'package:wanderai_mobile/features/places/data/navigation_service.dart';
import 'package:wanderai_mobile/features/places/data/youtube_update_model.dart';
import 'package:wanderai_mobile/features/places/presentation/place_detail_screen.dart';
import 'package:wanderai_mobile/features/places/providers/place_detail_provider.dart';

const _clockTowerId = '65562a67-84ff-44a0-990d-31917a2a9bd0';
const _haLongDestId = '4eec2f30-b67d-4221-b754-8fcc7bb1160e';

class _YoutubeTestBackendAdapter implements HttpClientAdapter {
  final Future<ResponseBody> Function(RequestOptions options)? onYoutubePlace;
  final Future<ResponseBody> Function(RequestOptions options)? onYoutubeDest;
  int placeYoutubeCalls = 0;
  int destYoutubeCalls = 0;

  _YoutubeTestBackendAdapter({
    this.onYoutubePlace,
    this.onYoutubeDest,
  });

  static Map<String, dynamic> get clockTowerPlaceJson => {
        'id': _clockTowerId,
        'name': 'Tháp Đồng Hồ',
        'nameEn': 'Ha Long Clock Tower',
        'description':
            'Tháp Đồng Hồ tại ngã 5 Bến Đoan là điểm nhận diện trung tâm thành phố Hạ Long.',
        'address': 'Ngã 5 Bến Đoan, Phường Bạch Đằng, Hạ Long, Quảng Ninh',
        'latitude': 20.9516105,
        'longitude': 107.0851999,
        'rating': 4.6,
        'reviewCount': 18,
        'isVerified': true,
        'provenanceCount': 2,
        'category': {'name': 'attraction'},
        'destination': {
          'id': _haLongDestId,
          'name': 'Hạ Long',
          'slug': 'ha-long',
        },
        'source': {
          'name': 'OpenStreetMap',
          'sourceId': 'way/674228542',
          'canonicalUrl': 'https://www.openstreetmap.org/way/674228542',
          'license': 'ODbL 1.0',
          'attribution': '© OpenStreetMap contributors',
        },
      };

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final method = options.method.toUpperCase();
    final path = options.path;

    if (method == 'GET' && path == '/places/$_clockTowerId') {
      return jsonResponse(200, {'success': true, 'data': clockTowerPlaceJson});
    }

    if (method == 'GET' && path == '/places/$_clockTowerId/youtube-updates') {
      placeYoutubeCalls++;
      if (onYoutubePlace != null) {
        return onYoutubePlace!(options);
      }
      return jsonResponse(404, {'message': 'Not mocked'});
    }

    if (method == 'GET' && path == '/destinations/ha-long/youtube-updates') {
      destYoutubeCalls++;
      if (onYoutubeDest != null) {
        return onYoutubeDest!(options);
      }
      return jsonResponse(404, {'message': 'Not mocked'});
    }

    if (method == 'GET' && path == '/trips') {
      return jsonResponse(200, {
        'success': true,
        'data': [
          {
            'id': 'trip-hl-1',
            'userId': 'u1',
            'destinationId': _haLongDestId,
            'title': 'Hành trình Hạ Long 2N1Đ',
            'status': 'PLANNED',
            'currency': 'VND',
            'itineraries': [],
          },
        ],
      });
    }

    if (method == 'GET' && path == '/users/me') {
      return jsonResponse(200, {
        'success': true,
        'data': {'id': 'u1', 'email': 'traveler@gomate.vn'},
      });
    }

    return jsonResponse(404, {'message': 'Unhandled $method $path'});
  }

  static ResponseBody jsonResponse(int code, Map<String, dynamic> payload) {
    return ResponseBody.fromString(
      jsonEncode(payload),
      code,
      headers: {
        Headers.contentTypeHeader: ['application/json'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Map<String, dynamic> _poiUpdateItem({
  String id = 'yt-poi-1',
  String? placeId = _clockTowerId,
  String scope = 'POI',
  required String publishedAt,
  required String receivedAt,
  String? updatedAt,
  int ingestLatencyMs = 12000,
  String title = 'Review Tháp Đồng Hồ Hạ Long buổi tối cực đẹp',
  String channelTitle = 'Hạ Long Explorer',
  String videoUrl = 'https://www.youtube.com/watch?v=hlClock2026',
}) {
  return {
    'id': id,
    'placeId': placeId,
    'destinationId': _haLongDestId,
    'destinationSlug': 'ha-long',
    'scope': scope,
    'source': 'youtube',
    'channelId': 'UC_HALONG_01',
    'channelTitle': channelTitle,
    'videoId': 'hlClock2026',
    'videoUrl': videoUrl,
    'title': title,
    'description': 'Cập nhật thực tế khu vực ngã 5 Bến Đoan.',
    'tags': ['ha-long', 'thap-dong-ho'],
    'publishedAt': publishedAt,
    'receivedAt': receivedAt,
    'updatedAt': updatedAt ?? receivedAt,
    'sourceUpdatedAt': updatedAt,
    'lastReceivedAt': receivedAt,
    'ingestLatencyMs': ingestLatencyMs,
    'deliveryLagMs': ingestLatencyMs,
    'groundingBasis': scope == 'CITY'
        ? 'DESTINATION_CITY_FALLBACK'
        : 'EXPLICIT_POI_REF_AND_TEXT_MATCH',
    'groundingEvidence': {'matched': true},
  };
}

Widget _buildScreen({
  required _YoutubeTestBackendAdapter backend,
  required DateTime fixedNow,
  List<Uri>? openedUrls,
}) {
  return ProviderScope(
    overrides: [
      youtubeClockProvider.overrideWithValue(() => fixedNow),
      if (openedUrls != null)
        externalUriOpenerProvider.overrideWithValue((uri) async {
          openedUrls.add(uri);
          return true;
        }),
      apiClientProvider.overrideWith((ref) {
        final epoch = ref.read(sessionEpochControllerProvider);
        return createApiClient(
          baseUrlOverride: 'http://localhost:3000',
          sessionEpoch: epoch,
        )..httpClientAdapter = backend;
      }),
    ],
    child: MaterialApp(
      theme: AppTheme.lightTheme,
      home: const PlaceDetailScreen(placeId: _clockTowerId),
    ),
  );
}

Future<void> _pump(WidgetTester tester, [int count = 6]) async {
  for (var i = 0; i < count; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  group('YoutubeUpdateModel & YoutubeUpdatesEnvelope contract parsing', () {
    test('parses 5 mandated fields, updatedAt fallback, and CITY nullability', () {
      final poi = YoutubeUpdateModel.fromJson({
        'id': 'u-poi',
        'placeId': _clockTowerId,
        'scope': 'POI',
        'source': 'youtube',
        'channelId': 'UC1',
        'videoId': 'vid1',
        'publishedAt': '2026-11-25T01:48:00.000Z',
        'receivedAt': '2026-11-25T01:48:12.000Z',
        'sourceUpdatedAt': '2026-11-25T01:48:05.000Z',
      });
      expect(poi.placeId, _clockTowerId);
      expect(poi.source, 'youtube');
      expect(poi.publishedAt, DateTime.utc(2026, 11, 25, 1, 48, 0));
      expect(poi.receivedAt, DateTime.utc(2026, 11, 25, 1, 48, 12));
      expect(poi.updatedAt, DateTime.utc(2026, 11, 25, 1, 48, 5));
      expect(poi.ingestLatencyMs, 12000);
      expect(poi.videoUrl, 'https://www.youtube.com/watch?v=vid1');

      final city = YoutubeUpdateModel.fromJson({
        'id': 'u-city',
        'placeId': 'should-be-cleared-for-city-scope',
        'scope': 'CITY',
        'source': 'youtube',
        'channelId': 'UC2',
        'videoId': 'vid2',
        'publishedAt': '2026-11-25T01:40:00.000Z',
        'receivedAt': '2026-11-25T01:40:10.000Z',
      });
      expect(city.isCityLevel, isTrue);
      expect(city.placeId, isNull);
      expect(city.updatedAt, city.receivedAt);

      // SLA boundaries: [0, 300000] -> Thời gian thực; >300000 or <0 -> Cập nhật gần đây
      expect(
        poi.freshnessBadgeLabelAt(DateTime.utc(2026, 11, 25, 1, 48, 0)),
        'Thời gian thực',
      );
      expect(
        poi.freshnessBadgeLabelAt(DateTime.utc(2026, 11, 25, 1, 53, 0)),
        'Thời gian thực',
      );
      expect(
        poi.freshnessBadgeLabelAt(DateTime.utc(2026, 11, 25, 1, 53, 0, 1)),
        'Cập nhật gần đây',
      );
      expect(
        poi.freshnessBadgeLabelAt(DateTime.utc(2026, 11, 25, 1, 47, 55)),
        'Cập nhật gần đây',
      );
    });

    test('GAP-11: malformed or missing publishedAt/receivedAt never masquerades as realtime', () {
      final receivedAt = DateTime.utc(2026, 11, 25, 1, 50, 0);
      final malformed = YoutubeUpdateModel.fromJson({
        'id': 'u-bad-date',
        'placeId': _clockTowerId,
        'scope': 'POI',
        'source': 'youtube',
        'channelId': 'UC1',
        'videoId': 'vidBad',
        'publishedAt': 'not-a-date',
        'receivedAt': receivedAt.toIso8601String(),
      });

      expect(malformed.hasValidPublishedAt, isFalse);
      expect(malformed.hasValidReceivedAt, isTrue);
      expect(malformed.publishedAt, isNot(receivedAt));
      expect(malformed.isRealtimeAt(receivedAt), isFalse);
      expect(malformed.freshnessBadgeLabelAt(receivedAt), 'Cập nhật gần đây');

      final missingBoth = YoutubeUpdateModel.fromJson({
        'id': 'u-missing-dates',
        'placeId': _clockTowerId,
        'scope': 'POI',
        'source': 'youtube',
        'channelId': 'UC1',
        'videoId': 'vidMissing',
      });
      expect(missingBoth.hasValidPublishedAt, isFalse);
      expect(missingBoth.hasValidReceivedAt, isFalse);
      expect(
        missingBoth.isRealtimeAt(DateTime.fromMillisecondsSinceEpoch(0, isUtc: true)),
        isFalse,
      );
      expect(
        missingBoth.freshnessBadgeLabelAt(
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
        ),
        'Cập nhật gần đây',
      );
    });
  });

  group('PlaceDetailScreen YouTube freshness UI', () {
    testWidgets(
      '(a) Tháp Đồng Hồ renders 5 mandated fields, clickable video URL, and governance separation',
      (tester) async {
        SharedPreferences.setMockInitialValues({});
        final openedUrls = <Uri>[];
        final fixedNow = DateTime.utc(2026, 11, 25, 1, 50, 0);
        final backend = _YoutubeTestBackendAdapter(
          onYoutubePlace: (_) async => _YoutubeTestBackendAdapter.jsonResponse(
            200,
            {
              'success': true,
              'data': {
                'placeId': _clockTowerId,
                'placeName': 'Tháp Đồng Hồ',
                'destinationId': _haLongDestId,
                'destinationSlug': 'ha-long',
                'destinationName': 'Hạ Long',
                'governanceRole': 'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
                'notPrimaryFactualCorpus': true,
                'serverDeliveredAt': '2026-11-25T01:49:30.000Z',
                'realtimeSlaMaxLatencyMs': 300000,
                'total': 1,
                'items': [
                  _poiUpdateItem(
                    publishedAt: '2026-11-25T01:49:15.000Z',
                    receivedAt: '2026-11-25T01:49:27.000Z',
                    updatedAt: '2026-11-25T01:49:20.000Z',
                  ),
                ],
                'cityFallbackTotal': 0,
                'cityFallbackItems': [],
              },
            },
          ),
        );

        await tester.pumpWidget(
          _buildScreen(
            backend: backend,
            fixedNow: fixedNow,
            openedUrls: openedUrls,
          ),
        );
        await _pump(tester, 8);

        final section = find.byKey(const Key('place_youtube_freshness_section'));
        await tester.ensureVisible(section);
        await _pump(tester, 2);

        expect(find.text('Cập nhật cộng đồng từ YouTube'), findsOneWidget);
        expect(find.text('Cập nhật xã hội · YouTube'), findsOneWidget);
        expect(
          find.textContaining('DYNAMIC_SOCIAL_FRESHNESS_LAYER'),
          findsOneWidget,
        );
        expect(
          find.textContaining('tách biệt khỏi dữ liệu xác minh OSM/Wikipedia'),
          findsOneWidget,
        );
        expect(find.text('place_id: $_clockTowerId'), findsOneWidget);
        expect(find.text('Nguồn: youtube · Hạ Long Explorer'), findsOneWidget);
        expect(find.textContaining('Xuất bản:'), findsOneWidget);
        expect(find.textContaining('Tiếp nhận:'), findsOneWidget);
        expect(find.textContaining('Cập nhật:'), findsOneWidget);
        expect(find.text('Thời gian thực'), findsOneWidget);
        expect(find.text('Cập nhật gần đây'), findsNothing);
        expect(find.textContaining('Độ trễ nguồn tới app: 45.0s'), findsOneWidget);
        expect(find.textContaining('Tiếp nhận server: 12.0s'), findsOneWidget);

        await tester.ensureVisible(
          find.byKey(const Key('youtube_video_link_yt-poi-1')),
        );
        await tester.tap(find.byKey(const Key('youtube_video_link_yt-poi-1')));
        await _pump(tester, 2);
        expect(
          openedUrls.map((u) => u.toString()),
          ['https://www.youtube.com/watch?v=hlClock2026'],
        );
      },
    );

    testWidgets(
      '(b) Hạ Long city-level fallback displays when POI items empty (inline & destination endpoint fallback)',
      (tester) async {
        SharedPreferences.setMockInitialValues({});
        final fixedNow = DateTime.utc(2026, 11, 25, 1, 50, 0);
        final backend = _YoutubeTestBackendAdapter(
          onYoutubePlace: (_) async => _YoutubeTestBackendAdapter.jsonResponse(
            200,
            {
              'success': true,
              'data': {
                'placeId': _clockTowerId,
                'placeName': 'Tháp Đồng Hồ',
                'destinationId': _haLongDestId,
                'destinationSlug': 'ha-long',
                'destinationName': 'Hạ Long',
                'governanceRole': 'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
                'notPrimaryFactualCorpus': true,
                'serverDeliveredAt': '2026-11-25T01:49:30.000Z',
                'realtimeSlaMaxLatencyMs': 300000,
                'total': 0,
                'items': [],
                'cityFallbackTotal': 0,
                'cityFallbackItems': [],
              },
            },
          ),
          onYoutubeDest: (options) async {
            expect(options.queryParameters['scope'], 'CITY');
            return _YoutubeTestBackendAdapter.jsonResponse(200, {
              'success': true,
              'data': {
                'destinationId': _haLongDestId,
                'destinationSlug': 'ha-long',
                'destinationName': 'Hạ Long',
                'governanceRole': 'DYNAMIC_SOCIAL_FRESHNESS_LAYER',
                'notPrimaryFactualCorpus': true,
                'serverDeliveredAt': '2026-11-25T01:49:30.000Z',
                'realtimeSlaMaxLatencyMs': 300000,
                'total': 1,
                'items': [
                  _poiUpdateItem(
                    id: 'yt-city-1',
                    placeId: null,
                    scope: 'CITY',
                    title: 'Toàn cảnh thành phố Hạ Long cuối tuần',
                    publishedAt: '2026-11-25T01:40:00.000Z',
                    receivedAt: '2026-11-25T01:40:15.000Z',
                  ),
                ],
                'cityFallbackTotal': 1,
                'cityFallbackItems': [
                  _poiUpdateItem(
                    id: 'yt-city-1',
                    placeId: null,
                    scope: 'CITY',
                    title: 'Toàn cảnh thành phố Hạ Long cuối tuần',
                    publishedAt: '2026-11-25T01:40:00.000Z',
                    receivedAt: '2026-11-25T01:40:15.000Z',
                  ),
                ],
              },
            });
          },
        );

        await tester.pumpWidget(_buildScreen(backend: backend, fixedNow: fixedNow));
        await _pump(tester, 8);

        await tester.ensureVisible(
          find.byKey(const Key('place_youtube_freshness_section')),
        );
        await _pump(tester, 2);

        expect(backend.destYoutubeCalls, 1);
        expect(find.byKey(const Key('youtube_city_fallback_banner')), findsOneWidget);
        expect(find.textContaining('Cập nhật cấp thành phố: Hạ Long'), findsWidgets);
        expect(find.text('place_id: null (cấp thành phố)'), findsOneWidget);
        expect(find.text('Toàn cảnh thành phố Hạ Long cuối tuần'), findsOneWidget);
      },
    );

    testWidgets(
      '(c) Latency SLA shows "Cập nhật gần đây" when > 300000ms or negative clock skew',
      (tester) async {
        SharedPreferences.setMockInitialValues({});
        final fixedNow = DateTime.utc(2026, 11, 25, 1, 50, 0);
        final backend = _YoutubeTestBackendAdapter(
          onYoutubePlace: (_) async => _YoutubeTestBackendAdapter.jsonResponse(
            200,
            {
              'success': true,
              'data': {
                'placeId': _clockTowerId,
                'placeName': 'Tháp Đồng Hồ',
                'destinationName': 'Hạ Long',
                'serverDeliveredAt': '2026-11-25T01:49:30.000Z',
                'realtimeSlaMaxLatencyMs': 300000,
                'total': 2,
                'items': [
                  _poiUpdateItem(
                    id: 'yt-stale',
                    publishedAt: '2026-11-25T01:43:00.000Z', // 7 min ago
                    receivedAt: '2026-11-25T01:43:15.000Z',
                    ingestLatencyMs: 15000,
                  ),
                  _poiUpdateItem(
                    id: 'yt-skew',
                    publishedAt: '2026-11-25T01:50:10.000Z', // -10s clock skew
                    receivedAt: '2026-11-25T01:50:12.000Z',
                    ingestLatencyMs: 2000,
                  ),
                ],
                'cityFallbackTotal': 0,
                'cityFallbackItems': [],
              },
            },
          ),
        );

        await tester.pumpWidget(_buildScreen(backend: backend, fixedNow: fixedNow));
        await _pump(tester, 8);

        await tester.ensureVisible(
          find.byKey(const Key('place_youtube_freshness_section')),
        );
        await _pump(tester, 2);

        expect(find.text('Thời gian thực'), findsNothing);
        expect(find.text('Cập nhật gần đây'), findsNWidgets(2));
        expect(find.textContaining('Độ trễ nguồn tới app: 7.0 phút'), findsOneWidget);
        expect(find.textContaining('-10000 ms (lệch đồng hồ)'), findsOneWidget);
      },
    );

    testWidgets(
      '(d) Loading & error isolation keeps PlaceDetailScreen and SavePlaceToTripSheet usable + retry recovers',
      (tester) async {
        SharedPreferences.setMockInitialValues({'access_token': 'tok'});
        final fixedNow = DateTime.utc(2026, 11, 25, 1, 50, 0);
        final pending = Completer<ResponseBody>();
        var shouldFail = true;

        final backend = _YoutubeTestBackendAdapter(
          onYoutubePlace: (_) {
            if (!pending.isCompleted) {
              return pending.future;
            }
            if (shouldFail) {
              return Future.value(
                _YoutubeTestBackendAdapter.jsonResponse(500, {
                  'success': false,
                  'message': 'Upstream down',
                }),
              );
            }
            return Future.value(
              _YoutubeTestBackendAdapter.jsonResponse(200, {
                'success': true,
                'data': {
                  'placeId': _clockTowerId,
                  'placeName': 'Tháp Đồng Hồ',
                  'destinationName': 'Hạ Long',
                  'serverDeliveredAt': '2026-11-25T01:49:30.000Z',
                  'realtimeSlaMaxLatencyMs': 300000,
                  'total': 1,
                  'items': [
                    _poiUpdateItem(
                      publishedAt: '2026-11-25T01:49:15.000Z',
                      receivedAt: '2026-11-25T01:49:25.000Z',
                    ),
                  ],
                  'cityFallbackTotal': 0,
                  'cityFallbackItems': [],
                },
              }),
            );
          },
        );

        await tester.pumpWidget(_buildScreen(backend: backend, fixedNow: fixedNow));
        await _pump(tester, 6);

        // 1. While YouTube updates are loading, PlaceDetail factual info & Save CTA remain rendered.
        expect(find.text('Tháp Đồng Hồ'), findsOneWidget);
        expect(find.text('Nguồn: OpenStreetMap'), findsOneWidget);
        expect(find.byKey(const Key('place_detail_save_to_trip')), findsOneWidget);
        await tester.ensureVisible(
          find.byKey(const Key('place_youtube_freshness_section')),
        );
        await _pump(tester, 2);
        expect(find.byKey(const Key('youtube_updates_loading')), findsOneWidget);

        // 2. When YouTube endpoint fails 500, non-blocking warning banner renders with Retry.
        pending.complete(
          _YoutubeTestBackendAdapter.jsonResponse(500, {
            'success': false,
            'message': 'Upstream down',
          }),
        );
        await _pump(tester, 6);

        final bannerFinder = find.byKey(const Key('youtube_updates_error_banner'));
        expect(bannerFinder, findsOneWidget);
        expect(
          tester.widget<AppStateBanner>(bannerFinder).tone,
          AppStateBannerTone.warning,
        );
        expect(find.byKey(const Key('place_detail_save_to_trip')), findsOneWidget);

        // 3. Tapping Retry recovers and renders POI item.
        shouldFail = false;
        await tester.ensureVisible(find.text('Thử lại'));
        await tester.tap(find.text('Thử lại'));
        await _pump(tester, 6);

        expect(find.byKey(const Key('youtube_updates_error_banner')), findsNothing);
        expect(find.text('place_id: $_clockTowerId'), findsOneWidget);
        expect(find.text('Thời gian thực'), findsOneWidget);
      },
    );

    testWidgets(
      'GAP-11: malformed publishedAt renders fallback text and never shows "Thời gian thực"',
      (tester) async {
        SharedPreferences.setMockInitialValues({});
        final fixedNow = DateTime.utc(2026, 11, 25, 1, 50, 0);
        final backend = _YoutubeTestBackendAdapter(
          onYoutubePlace: (_) async => _YoutubeTestBackendAdapter.jsonResponse(
            200,
            {
              'success': true,
              'data': {
                'placeId': _clockTowerId,
                'placeName': 'Tháp Đồng Hồ',
                'destinationName': 'Hạ Long',
                'serverDeliveredAt': '2026-11-25T01:50:00.000Z',
                'realtimeSlaMaxLatencyMs': 300000,
                'total': 1,
                'items': [
                  _poiUpdateItem(
                    id: 'yt-malformed',
                    publishedAt: 'not-a-date',
                    receivedAt: '2026-11-25T01:50:00.000Z',
                    ingestLatencyMs: 0,
                  ),
                ],
                'cityFallbackTotal': 0,
                'cityFallbackItems': [],
              },
            },
          ),
        );

        await tester.pumpWidget(_buildScreen(backend: backend, fixedNow: fixedNow));
        await _pump(tester, 8);

        await tester.ensureVisible(
          find.byKey(const Key('place_youtube_freshness_section')),
        );
        await _pump(tester, 2);

        expect(find.text('Thời gian thực'), findsNothing);
        expect(find.text('Cập nhật gần đây'), findsOneWidget);
        expect(find.text('Xuất bản: Không rõ thời điểm xuất bản'), findsOneWidget);
      },
    );
  });
}
