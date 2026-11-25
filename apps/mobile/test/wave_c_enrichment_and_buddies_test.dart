import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/places/presentation/place_detail_screen.dart';
import 'package:wanderai_mobile/features/safety/data/buddy_models.dart';
import 'package:wanderai_mobile/features/safety/data/buddy_repository.dart';
import 'package:wanderai_mobile/features/safety/presentation/safety_and_buddies_screen.dart';
import 'package:wanderai_mobile/features/safety/providers/buddy_provider.dart';

class _FakeBuddyRepo implements BuddyRepository {
  bool isDiscoverable;
  final bool shouldFailLoad;
  final List<BuddyCandidateModel> candidates;
  final List<BuddyMatchRecord> matches;
  final List<String> requestedIds = [];
  final List<String> withdrawnIds = [];
  final List<String> blockedIds = [];
  final List<(String, String)> responses = [];

  _FakeBuddyRepo({
    this.isDiscoverable = true,
    this.shouldFailLoad = false,
    this.candidates = const [],
    this.matches = const [],
  });

  @override
  Future<bool> getDiscoveryConsent() async => isDiscoverable;

  @override
  Future<bool> updateDiscoveryConsent(bool value) async {
    isDiscoverable = value;
    return isDiscoverable;
  }

  @override
  Future<BuddyCandidatesResponse> getCandidatesWithConsent({
    String? destinationId,
    int limit = 20,
  }) async {
    if (shouldFailLoad) {
      throw Exception('Network error');
    }
    return BuddyCandidatesResponse(
      isDiscoverable: isDiscoverable,
      items: isDiscoverable ? candidates : const [],
    );
  }

  @override
  Future<List<BuddyCandidateModel>> getCandidates({
    String? destinationId,
    int limit = 20,
  }) async =>
      isDiscoverable ? candidates : const [];

  @override
  Future<BuddyMaskedProfileModel> getMaskedProfile(String peerId) async {
    final cand = candidates.firstWhere((c) => c.peer.id == peerId);
    return BuddyMaskedProfileModel(
      peer: cand.peer,
      compatibilityScore: cand.compatibilityScore,
      compatibilityBand: cand.compatibilityBand,
      sharedInterests: cand.sharedInterests,
      sharedDestinationNames: cand.sharedDestinationNames,
      hasOverlappingTripWindow: true,
      explanation: cand.explanation,
      plannedDestinations: const [
        BuddyPlannedDestinationSummary(
          destinationId: 'dest-dn',
          destinationName: 'Đà Nẵng',
          hasOverlappingWindow: true,
        ),
      ],
    );
  }

  @override
  Future<List<BuddyMatchRecord>> getMyMatches() async {
    if (shouldFailLoad) {
      throw Exception('Network error');
    }
    return matches;
  }

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
  Future<BuddyMatchRecord> withdrawRequest(String matchId) async {
    withdrawnIds.add(matchId);
    return BuddyMatchRecord(
      id: matchId,
      status: 'WITHDRAWN',
      direction: 'SENT',
      peer: const BuddyPeerModel(id: 'peer-out', displayName: 'Quốc Bảo'),
    );
  }

  @override
  Future<BuddyMatchRecord> respond(String matchId, String action) async {
    responses.add((matchId, action));
    return matches.first;
  }

  @override
  Future<void> blockUser(String blockedUserId) async {
    blockedIds.add(blockedUserId);
  }
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
          'coverImage':
              'https://upload.wikimedia.org/example/vanmieu_cover.jpg',
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
            'descriptionSourceUrl':
                'https://vi.wikipedia.org/wiki/V%C4%83n_Mi%E1%BA%BFu',
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
        expect(
          find.text('Không gian trang nghiêm, nhiều cây xanh mát.'),
          findsOneWidget,
        );

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
      },
    );
  });

  group('W08 Buddy Matching & Safety Tab (/safety)', () {
    testWidgets(
      'supports opt-in toggle, masked profile sheet, invite/withdraw/accept actions, and SOS hotlines',
      (tester) async {
        final repo = _FakeBuddyRepo(
          isDiscoverable: false,
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
              explanation:
                  'Cùng sở thích: Ẩm thực, Văn hóa · Cùng kế hoạch đến Đà Nẵng',
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
            BuddyMatchRecord(
              id: 'match-out-1',
              status: 'PENDING',
              direction: 'SENT',
              score: 70,
              peer: BuddyPeerModel(id: 'peer-4', displayName: 'Quốc Bảo'),
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

        // Initially opt-in is off -> scroll down to verify opt-in empty state is shown
        final optOffFinder = find.byKey(const Key('buddy_opt_in_off_state'));
        await tester.scrollUntilVisible(
          optOffFinder,
          180,
          scrollable: find.byType(Scrollable).first,
        );
        expect(optOffFinder, findsOneWidget);

        // Scroll back up and turn opt-in ON via SwitchListTile
        final switchFinder = find.byKey(const Key('buddy_discovery_switch'));
        await tester.scrollUntilVisible(
          switchFinder,
          -180,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.ensureVisible(switchFinder);
        await tester.pumpAndSettle();
        await tester.tap(switchFinder);
        await tester.pumpAndSettle();

        // Accept incoming PENDING request
        final acceptBtn = find.byKey(const Key('match_accept_match-in-1'));
        await tester.ensureVisible(acceptBtn);
        await tester.tap(acceptBtn);
        await tester.pumpAndSettle();
        expect(repo.responses, [('match-in-1', 'ACCEPTED')]);

        // Withdraw outgoing PENDING request
        final withdrawBtn = find.byKey(const Key('match_withdraw_match-out-1'));
        await tester.ensureVisible(withdrawBtn);
        await tester.tap(withdrawBtn);
        await tester.pumpAndSettle();
        expect(repo.withdrawnIds, ['match-out-1']);

        // Scroll to candidate Minh Khôi and open masked profile sheet
        final openProfileBtn =
            find.byKey(const Key('buddy_open_profile_peer-2'));
        await tester.scrollUntilVisible(
          openProfileBtn,
          180,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.ensureVisible(openProfileBtn);
        await tester.pumpAndSettle();
        expect(find.text('Minh Khôi'), findsOneWidget);
        expect(find.text('84% hợp nhau'), findsOneWidget);
        await tester.tap(openProfileBtn);
        await tester.pumpAndSettle();

        expect(
          find.byKey(const Key('buddy_masked_profile_sheet')),
          findsOneWidget,
        );
        expect(find.text('Đà Nẵng (Trùng lịch)'), findsOneWidget);

        // Invite directly from masked profile sheet
        await tester.tap(find.byKey(const Key('buddy_sheet_invite_peer-2')));
        await tester.pumpAndSettle();
        expect(repo.requestedIds, ['peer-2']);

        // Switch to An toàn & SOS view
        await tester.tap(find.text('An toàn & SOS'));
        await tester.pumpAndSettle();
        expect(find.textContaining('113'), findsOneWidget);
        expect(find.textContaining('114'), findsOneWidget);
        expect(find.textContaining('115'), findsOneWidget);
      },
    );

    testWidgets('renders honest error state with retry when backend load fails',
        (tester) async {
      final repo = _FakeBuddyRepo(shouldFailLoad: true);
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
      expect(
        find.text('Không thể tải danh sách bạn đồng hành.'),
        findsOneWidget,
      );
    });
  });

  group('GAP-19: BuddyNotifier mid-flight disposal safety', () {
    const sampleRecord = BuddyMatchRecord(
      id: 'm-1',
      status: 'PENDING',
      direction: 'SENT',
      score: 85,
      peer: BuddyPeerModel(id: 'u-2', displayName: 'Minh Khôi'),
    );

    DioException makeDioError(String path) => DioException(
          requestOptions: RequestOptions(path: path),
          type: DioExceptionType.connectionError,
        );

    test(
        'sendRequest() and respond() disposed mid-flight throw 0 StateErrors and return accurate status',
        () async {
      for (final shouldReject in [false, true]) {
        final repo = _DeferredBuddyRepo()
          ..sendCompleter = Completer<BuddyMatchRecord>()
          ..respondCompleter = Completer<BuddyMatchRecord>();
        final notifier = BuddyNotifier(repo);

        final sendFuture = notifier.sendRequest('u-2');
        final respondFuture = notifier.respond('m-1', 'ACCEPT');
        notifier.dispose();

        if (shouldReject) {
          repo.sendCompleter!.completeError(makeDioError('/matches/request'));
          repo.respondCompleter!
              .completeError(makeDioError('/matches/m-1/respond'));
        } else {
          repo.sendCompleter!.complete(sampleRecord);
          repo.respondCompleter!.complete(sampleRecord);
        }

        expect(await sendFuture, !shouldReject);
        expect(await respondFuture, !shouldReject);
        expect(repo.loadCalls, 0);
      }
    });

    test(
        'load() triggered inside sendRequest()/respond() handles mid-flight dispose cleanly on resolve and reject',
        () async {
      for (final shouldRejectLoad in [false, true]) {
        final repo = _DeferredBuddyRepo()
          ..sendCompleter = Completer<BuddyMatchRecord>()
          ..candidatesCompleter = Completer<List<BuddyCandidateModel>>()
          ..matchesCompleter = Completer<List<BuddyMatchRecord>>();
        final notifier = BuddyNotifier(repo);

        final sendFuture = notifier.sendRequest('u-2');
        repo.sendCompleter!.complete(sampleRecord);
        await Future<void>.delayed(Duration.zero);

        notifier.dispose();
        if (shouldRejectLoad) {
          repo.candidatesCompleter!
              .completeError(makeDioError('/matches/candidates'));
          repo.matchesCompleter!.completeError(makeDioError('/matches'));
        } else {
          repo.candidatesCompleter!.complete(const []);
          repo.matchesCompleter!.complete(const [sampleRecord]);
        }

        expect(await sendFuture, isTrue);
      }
    });
  });
}

class _DeferredBuddyRepo implements BuddyRepository {
  Completer<BuddyMatchRecord>? sendCompleter;
  Completer<BuddyMatchRecord>? respondCompleter;
  Completer<List<BuddyCandidateModel>>? candidatesCompleter;
  Completer<List<BuddyMatchRecord>>? matchesCompleter;
  int loadCalls = 0;

  @override
  Future<List<BuddyCandidateModel>> getCandidates({
    String? destinationId,
    int limit = 20,
  }) {
    loadCalls++;
    if (candidatesCompleter != null) return candidatesCompleter!.future;
    return Future.value(const []);
  }

  @override
  Future<BuddyCandidatesResponse> getCandidatesWithConsent({
    String? destinationId,
    int limit = 20,
  }) async {
    final items = await getCandidates(
      destinationId: destinationId,
      limit: limit,
    );
    return BuddyCandidatesResponse(isDiscoverable: true, items: items);
  }

  @override
  Future<List<BuddyMatchRecord>> getMyMatches() {
    if (matchesCompleter != null) return matchesCompleter!.future;
    return Future.value(const []);
  }

  @override
  Future<BuddyMatchRecord> sendRequest(String receiverId) {
    if (sendCompleter != null) return sendCompleter!.future;
    return Future.error(Exception('missing completer'));
  }

  @override
  Future<BuddyMatchRecord> respond(String matchId, String action) {
    if (respondCompleter != null) return respondCompleter!.future;
    return Future.error(Exception('missing completer'));
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
