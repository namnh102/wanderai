import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/material.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/map/providers/map_provider.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/place_preview_sheet.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/map_category_bar.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/map_search_bar.dart';
import 'package:wanderai_mobile/features/map/presentation/widgets/map_radius_selector.dart';

// ── Test Data ──
final _samplePlace = PlaceModel.fromJson({
  'id': '00000000-0000-0000-0000-000000000001',
  'name': 'Cầu Rồng',
  'nameEn': 'Dragon Bridge',
  'address': 'Nguyễn Văn Linh, Đà Nẵng',
  'latitude': 16.0612,
  'longitude': 108.2272,
  'rating': 4.5,
  'reviewCount': 120,
  'categoryName': 'attraction',
  'destinationName': 'Đà Nẵng',
  'isVerified': true,
  'provenanceCount': 1,
  'distanceKm': 0.5,
});


void main() {
  group('PlaceModel', () {
    test('parses JSON from /places endpoint (with nested relations)', () {
      final place = PlaceModel.fromJson({
        'id': 'test-id',
        'name': 'Test Place',
        'nameEn': 'Test Place EN',
        'latitude': 21.0285,
        'longitude': 105.8542,
        'rating': 4.0,
        'category': {'id': 'cat-1', 'name': 'restaurant', 'icon': 'restaurant', 'color': '#FF5722'},
        'destination': {'id': 'dest-1', 'name': 'Hà Nội', 'slug': 'ha-noi', 'province': 'Hà Nội'},
        'placeSources': [{'sourceName': 'osm', 'sourceId': 'node/123', 'confidenceScore': 1.0}],
        'isVerified': true,
        'provenanceCount': 1,
      });

      expect(place.id, 'test-id');
      expect(place.name, 'Test Place');
      expect(place.categoryName, 'restaurant');
      expect(place.destinationName, 'Hà Nội');
      expect(place.isVerified, true);
      expect(place.hasCoordinates, true);
    });

    test('parses JSON from /places/nearby endpoint (flat SQL result)', () {
      final place = PlaceModel.fromJson({
        'id': 'nearby-id',
        'name': 'Nearby Place',
        'nameEn': 'Nearby EN',
        'latitude': 16.06,
        'longitude': 108.22,
        'rating': 3.5,
        'reviewCount': 10,
        'categoryName': 'hotel',
        'destinationName': 'Đà Nẵng',
        'isVerified': true,
        'distanceKm': 2.5,
      });

      expect(place.id, 'nearby-id');
      expect(place.categoryName, 'hotel');
      expect(place.distanceKm, 2.5);
      expect(place.isVerified, true);
    });

    test('handles missing coordinates gracefully', () {
      final place = PlaceModel.fromJson({
        'id': 'no-coords',
        'name': 'No Coords Place',
      });

      expect(place.hasCoordinates, false);
      expect(place.latitude, isNull);
      expect(place.longitude, isNull);
    });

    test('missing rating stays null (unavailable) and reviewCount defaults to 0', () {
      final place = PlaceModel.fromJson({
        'id': 'defaults',
        'name': 'Default Place',
      });

      expect(place.rating, isNull);
      expect(place.reviewCount, 0);
      expect(place.isVerified, false);
    });
  });

  group('MapState', () {
    test('initial state has default center (Hanoi)', () {
      const state = MapState();
      expect(state.status, MapLoadingStatus.initial);
      expect(state.center.latitude, closeTo(21.0285, 0.001));
      expect(state.center.longitude, closeTo(105.8542, 0.001));
      expect(state.places, isEmpty);
      expect(state.selectedPlace, isNull);
      expect(state.selectedCategory, isNull);
      expect(state.radiusKm, 10.0);
    });

    test('copyWith preserves unmodified fields', () {
      const state = MapState(radiusKm: 5.0, useLocation: true);
      final updated = state.copyWith(status: MapLoadingStatus.loaded);

      expect(updated.status, MapLoadingStatus.loaded);
      expect(updated.radiusKm, 5.0);
      expect(updated.useLocation, true);
    });

    test('copyWith can clear optional fields', () {
      final state = MapState(
        selectedPlace: _samplePlace,
        selectedCategory: 'hotel',
        searchQuery: 'test',
      );

      final cleared = state.copyWith(
        clearSelectedPlace: true,
        clearCategory: true,
        clearSearch: true,
      );

      expect(cleared.selectedPlace, isNull);
      expect(cleared.selectedCategory, isNull);
      expect(cleared.searchQuery, isNull);
    });
  });

  group('MapCategoryBar widget', () {
    testWidgets('renders all categories', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: MapCategoryBar(
            selectedCategory: null,
            onCategorySelected: (_) {},
          ),
        ),
      ));

      // "Tất cả" should be visible
      expect(find.text('Tất cả'), findsOneWidget);
      expect(find.text('Tham quan'), findsOneWidget);
      expect(find.text('Nhà hàng'), findsOneWidget);
      expect(find.text('Khách sạn'), findsOneWidget);
    });

    testWidgets('fires callback on tap', (tester) async {
      String? selected;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: MapCategoryBar(
            selectedCategory: null,
            onCategorySelected: (cat) => selected = cat,
          ),
        ),
      ));

      await tester.tap(find.text('Nhà hàng'));
      expect(selected, 'restaurant');
    });
  });

  group('PlacePreviewSheet widget', () {
    testWidgets('displays place name and category', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PlacePreviewSheet(
            place: _samplePlace,
            onClose: () {},
          ),
        ),
      ));

      expect(find.text('Cầu Rồng'), findsOneWidget);
      expect(find.text('Tham quan'), findsOneWidget);
    });

    testWidgets('displays rating when present', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PlacePreviewSheet(
            place: _samplePlace,
            onClose: () {},
          ),
        ),
      ));

      expect(find.text('4.5'), findsOneWidget);
    });

    testWidgets('shows honest unavailable-rating label when rating is null', (tester) async {
      final unrated = PlaceModel.fromJson({
        'id': 'unrated',
        'name': 'Quán chưa có đánh giá',
        'latitude': 16.06,
        'longitude': 108.22,
      });
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PlacePreviewSheet(place: unrated, onClose: () {}),
        ),
      ));

      expect(find.text('Chưa có đánh giá'), findsOneWidget);
      expect(find.text('0.0'), findsNothing);
      expect(find.text('4.5'), findsNothing);
    });

    testWidgets('shows Vietnamese labels for TASK 07.4 categories', (tester) async {
      const expected = {'culture': 'Văn hóa', 'nature': 'Thiên nhiên', 'entertainment': 'Giải trí'};
      for (final e in expected.entries) {
        final p = PlaceModel.fromJson({
          'id': e.key,
          'name': 'Địa điểm ${e.key}',
          'latitude': 16.06,
          'longitude': 108.22,
          'category': {'name': e.key},
        });
        await tester.pumpWidget(MaterialApp(
          home: Scaffold(body: PlacePreviewSheet(place: p, onClose: () {})),
        ));
        expect(find.text(e.value), findsWidgets, reason: e.key);
        expect(find.text(e.key), findsNothing, reason: 'raw key leaked for ${e.key}');
      }
    });

    testWidgets('displays distance when present', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PlacePreviewSheet(
            place: _samplePlace,
            onClose: () {},
          ),
        ),
      ));

      expect(find.text('500m'), findsOneWidget);
    });

    testWidgets('displays verified badge when isVerified', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PlacePreviewSheet(
            place: _samplePlace,
            onClose: () {},
          ),
        ),
      ));

      expect(find.text('Đã xác minh'), findsOneWidget);
    });

    testWidgets('displays address when present', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PlacePreviewSheet(
            place: _samplePlace,
            onClose: () {},
          ),
        ),
      ));

      expect(find.text('Nguyễn Văn Linh, Đà Nẵng'), findsOneWidget);
    });

    testWidgets('close button fires callback', (tester) async {
      bool closed = false;
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: PlacePreviewSheet(
            place: _samplePlace,
            onClose: () => closed = true,
          ),
        ),
      ));

      await tester.tap(find.byIcon(Icons.close));
      expect(closed, true);
    });
  });

  group('MapSearchBar widget', () {
    testWidgets('renders with hint text', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: MapSearchBar(
            onSearch: (_) {},
            onClear: () {},
          ),
        ),
      ));

      expect(find.text('Tìm địa điểm...'), findsOneWidget);
    });
  });

  group('MapRadiusSelector widget', () {
    testWidgets('displays current radius', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: MapRadiusSelector(
            currentRadius: 10.0,
            onRadiusChanged: (_) {},
          ),
        ),
      ));

      expect(find.text('10km'), findsOneWidget);
    });
  });

  group('mapCategories', () {
    test('has "all" as first entry', () {
      expect(mapCategories.first.key, 'all');
      expect(mapCategories.first.label, 'Tất cả');
    });

    test('contains expected categories from backend taxonomy', () {
      final keys = mapCategories.map((c) => c.key).toSet();
      expect(keys, containsAll(['attraction', 'restaurant', 'hotel', 'culture', 'beach', 'nature', 'entertainment', 'cafe']));
    });

    test('does not contain non-existent categories', () {
      final keys = mapCategories.map((c) => c.key).toSet();
      expect(keys.contains('fake_category'), false);
    });
  });

  group('radiusOptions', () {
    test('contains expected values', () {
      expect(radiusOptions, [1.0, 5.0, 10.0, 25.0]);
    });
  });
}
