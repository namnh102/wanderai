import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/places/presentation/place_detail_screen.dart';
import 'package:wanderai_mobile/features/safety/data/buddy_models.dart';
import 'package:wanderai_mobile/features/safety/data/buddy_repository.dart';
import 'package:wanderai_mobile/features/safety/presentation/safety_and_buddies_screen.dart';

class _FakeBuddyRepo implements BuddyRepository {
  final List<BuddyCandidateModel> candidates;
  final List<BuddyMatchRecord> matches;
  final List<String> requestedIds = [];
  final List<(String, String)> responses = [];

  _FakeBuddyRepo({this.candidates = const [], this.matches = const []});

  @override
  Future<List<BuddyCandidateModel>> getCandidates({int limit = 20}) async =>
      candidates;

  @override
  Future<List<BuddyMatchRecord>> getMyMatches() async => matches;

  @override
  Future<BuddyMatchRecord> sendRequest(String receiverId) async {
    requestedIds.add(receiverId);
    return BuddyMatchRecord(
      id: 'm-new',
      status: 'PENDING',
      direction: 'SENT',
      score: 78,
      peer: candidates.first.peer,
    );
  }

  @override
  Future<BuddyMatchRecord> respond(String matchId, String action) async {
    responses.add((matchId, action));
    return matches.first;
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  group('Wave C POI Enrichment UI (gallery, attribution, reviews)', () {
    testWidgets(
        'PlaceDetailView renders Wikimedia gallery attribution, Wikipedia source, and traveler reviews',
        (tester) async {
      final place = PlaceModel.fromJson({
        'id': 'p-hn-1',
        'name': 'Văn Miếu Quốc Tử Giám',
        'description':
            'Quần thể di tích lịch sử văn hóa hàng đầu tại Hà Nội, trường đại học đầu tiên của Việt Nam.',
        'coverImage': 'https://upload.wikimedia.org/example/vanmieu_cover.jpg',
        'images': [
          'https://upload.wikimedia.org/example/vanmieu_cover.jpg',
          'https://upload.wikimedia.org/example/vanmieu_khuevancac.jpg',
        ],
        'rating': 4.8,
        'reviewCount': 1,
        'isVerified': true,
        'category': {'name': 'culture'},
        'destination': {'name': 'Hà Nội'},
        'enrichmentMeta': {
          'descriptionSourceUrl': 'https://vi.wikipedia.org/wiki/V%C4%83n_Mi%E1%BA%BFu',
          'descriptionLicense': 'CC BY-SA 4.0 (Wikipedia)',
          'imageAttributions': [
            {'license': 'CC BY-SA 4.0'},
          ],
        },
        'reviews': [
          {
            'id': 'rev-1',
            'rating': 5.0,
            'content': 'Không gian trang nghiêm, nhiều cây xanh mát.',
            'user': {
              'id': 'u-1',
              'profile': {'displayName': 'Lan Anh'},
            },
          },
        ],
      });

      final openedUrls = <String>[];
      var writeReviewTapped = false;

      await tester.pumpWidget(
        MaterialApp(
          theme: AppTheme.lightTheme,
          home: Scaffold(
            body: PlaceDetailView(
              place: place,
              onOpenUrl: openedUrls.add,
              onDirections: () {},
              onWriteReview: () => writeReviewTapped = true,
            ),
          ),
        ),
      );
      await tester.pump();

      expect(find.byKey(const Key('place_detail_gallery')), findsOneWidget);
      expect(find.textContaining('CC BY-SA 4.0'), findsWidgets);
      expect(find.text('Lan Anh'), findsOneWidget);
      expect(find.text('Không gian trang nghiêm, nhiều cây xanh mát.'), findsOneWidget);

      await tester.tap(find.byKey(const Key('place_detail_write_review')));
      expect(writeReviewTapped, isTrue);

      await tester.scrollUntilVisible(
        find.byKey(const Key('place_detail_wiki_source')),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(
        find.byKey(const Key('place_detail_wiki_source')),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('place_detail_wiki_source')));
      expect(
        openedUrls,
        contains('https://vi.wikipedia.org/wiki/V%C4%83n_Mi%E1%BA%BFu'),
      );
    });
  });

  group('Wave C W08 Buddy Matching & Safety Tab (/safety)', () {
    testWidgets(
        'renders privacy-safe buddy candidates, triggers request, and switches cleanly to SOS hotlines',
        (tester) async {
      final repo = _FakeBuddyRepo(
        candidates: const [
          BuddyCandidateModel(
            peer: BuddyPeerModel(
              id: 'peer-2',
              displayName: 'Minh Khôi',
              travelStyle: 'COMFORT',
              bio: 'Thích khám phá ẩm thực và bảo tàng.',
            ),
            compatibilityScore: 84,
            compatibilityBand: 'HIGH',
            explanation: 'Cùng sở thích: Ẩm thực, Văn hóa · Cùng kế hoạch đến Đà Nẵng',
          ),
        ],
        matches: const [
          BuddyMatchRecord(
            id: 'match-in-1',
            status: 'PENDING',
            direction: 'RECEIVED',
            score: 76,
            explanation: 'Cùng sở thích: Biển & Đảo',
            peer: BuddyPeerModel(id: 'peer-3', displayName: 'Thu Hà'),
          ),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [buddyRepositoryProvider.overrideWithValue(repo)],
          child: MaterialApp(
            theme: AppTheme.lightTheme,
            home: const SafetyAndBuddiesScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('An toàn & Bạn đồng hành'), findsOneWidget);
      expect(find.textContaining('email, số điện thoại'), findsOneWidget);
      expect(find.text('Thu Hà'), findsOneWidget);
      expect(find.text('Minh Khôi'), findsOneWidget);
      expect(find.text('84% hợp nhau'), findsOneWidget);

      final reqBtn = find.byKey(const Key('buddy_request_peer-2'));
      await tester.scrollUntilVisible(reqBtn, 200);
      await tester.ensureVisible(reqBtn);
      await tester.pumpAndSettle();
      await tester.tap(reqBtn);
      await tester.pumpAndSettle();
      expect(repo.requestedIds, ['peer-2']);

      // Switch to An toàn & SOS view
      await tester.tap(find.text('An toàn & SOS'));
      await tester.pumpAndSettle();
      expect(find.textContaining('113'), findsOneWidget);
      expect(find.textContaining('114'), findsOneWidget);
      expect(find.textContaining('115'), findsOneWidget);
    });
  });
}
