// Live TC-W3-01 acceptance check against a RUNNING stack (PostgreSQL + NestJS + FastAPI).
//
// Opt-in only: skipped unless `LIVE_W3=1` so CI (no backend) stays deterministic.
//   $env:LIVE_W3='1'; flutter test test/live_tc_w3_01_test.dart
//
// It drives the REAL mobile repositories (ProfileRepository / RecommendationRepository)
// over HTTP, i.e. the exact request path the app uses. No LLM is involved.
@TestOn('vm')
library;

import 'dart:convert';
import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wanderai_mobile/features/profile/data/profile_models.dart';
import 'package:wanderai_mobile/features/profile/data/profile_repository.dart';
import 'package:wanderai_mobile/features/recommendations/data/recommendation_repository.dart';

const _base = 'http://localhost:3000';

Dio _client([String? token]) => Dio(BaseOptions(
      baseUrl: _base,
      headers: token == null ? null : {'Authorization': 'Bearer $token'},
    ));

Future<String> _login(String email, String password) async {
  final res = await _client().post('/auth/login', data: {'email': email, 'password': password});
  return res.data['data']['access_token'] as String;
}

void main() {
  final live = Platform.environment['LIVE_W3'] == '1';

  test('TC-W3-01: preferences persist, re-login retains, Da Nang REC-A core only', () async {
    final stamp = DateTime.now().millisecondsSinceEpoch;
    final email = 'w302live_$stamp@wanderai.test';
    const password = 'AuditPass#123';
    await _client().post('/auth/register', data: {'email': email, 'password': password, 'name': 'W302 Live'});

    // 1. save preferences through the mobile ProfileRepository
    final session1 = _client(await _login(email, password));
    final profileRepo = ProfileRepository(session1);
    final saved = await profileRepo.updatePreferences(
      const TravelPreferences(interests: ['culture_history', 'food_cuisine']),
    );
    expect(saved.interests, ['culture_history', 'food_cuisine']);

    // 2. re-login (fresh token / fresh client) and re-fetch from PostgreSQL
    final session2 = _client(await _login(email, password));
    final reloaded = await ProfileRepository(session2).getProfile();
    expect(reloaded.preferences!.interests, ['culture_history', 'food_cuisine']);

    // Freeze V2 ground truth
    final freeze = jsonDecode(File('../../data/curated/gomate_places_freeze_v2.json').readAsStringSync(encoding: utf8))
        as List<dynamic>;
    final coreIds = {for (final p in freeze) if (p['is_rec_a_core_v2'] == true) p['place_id'] as String};
    final secondaryDn = [
      for (final p in freeze)
        if (p['is_rec_a_core_v2'] == false && p['destination_slug'] == 'da-nang') p
    ];
    expect(secondaryDn, hasLength(4));
    final secondaryIds = {for (final p in secondaryDn) p['place_id'] as String};

    // 3-5. Da Nang through the mobile RecommendationRepository
    final recoRepo = RecommendationRepository(session2);
    final dn = await recoRepo.fetch(destination: 'da-nang');
    expect(dn.recommendations.length, inInclusiveRange(1, 10));
    expect(dn.metadata.totalCandidates, 289);
    expect(dn.metadata.coldStart, isFalse);
    for (final r in dn.recommendations) {
      expect(r.destinationSlug, 'da-nang');
      expect(coreIds.contains(r.placeId), isTrue, reason: r.name);
      expect(secondaryIds.contains(r.placeId), isFalse, reason: r.name);
      // 6. reason from real REC-A taxonomy/features
      expect(r.explanation.reasonCode, 'PREFERENCE_TAXONOMY_MATCH');
      expect(r.explanation.matchedTaxonomy, isNotEmpty);
      expect(r.explanation.text, isNotEmpty);
      expect(['culture_history', 'food_cuisine'], containsAll(r.matchedInterests));
    }

    // 7-8. no fabricated rating and every result resolves to the existing Place Detail endpoint
    for (final r in dn.recommendations) {
      final detail = await session2.get('/places/${r.placeId}');
      final p = detail.data['data'] as Map<String, dynamic>;
      expect(p['rating'], isNull, reason: r.name);
      expect(p['reviewCount'], 0, reason: r.name);
    }

    // Smoke: Hà Nội and Hạ Long
    final hn = await recoRepo.fetch(destination: 'ha-noi');
    final hl = await recoRepo.fetch(destination: 'ha-long');
    expect(hn.metadata.totalCandidates, 145);
    expect(hl.metadata.totalCandidates, 188);
    expect(hn.recommendations.every((r) => r.destinationSlug == 'ha-noi' && coreIds.contains(r.placeId)), isTrue);
    expect(hl.recommendations.every((r) => r.destinationSlug == 'ha-long' && coreIds.contains(r.placeId)), isTrue);

    // Contract errors surface as readable text through the repository
    await expectLater(
      recoRepo.fetch(destination: 'Paris'),
      throwsA(isA<RecommendationException>().having((e) => e.message, 'message', contains('không được hỗ trợ'))),
    );
    // ignore: avoid_print
    print('TC-W3-01 LIVE OK: DN=${dn.recommendations.length} HN=${hn.recommendations.length} HL=${hl.recommendations.length}');
  }, skip: live ? false : 'set LIVE_W3=1 with the stack running');
}
