import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wanderai_mobile/core/theme/app_theme.dart';
import 'package:wanderai_mobile/core/widgets/app_empty_state.dart';
import 'package:wanderai_mobile/core/widgets/app_error_state.dart';
import 'package:wanderai_mobile/core/widgets/app_loading.dart';
import 'package:wanderai_mobile/features/home/data/home_models.dart';
import 'package:wanderai_mobile/features/home/presentation/widgets/destination_places_sheet.dart';
import 'package:wanderai_mobile/features/map/data/place_model.dart';
import 'package:wanderai_mobile/features/map/data/place_repository.dart';
import 'package:wanderai_mobile/features/map/providers/map_provider.dart';

class _ControllablePlaceRepo extends PlaceRepository {
  Future<List<PlaceModel>> Function({
    int page,
    int limit,
    String? search,
    String? category,
    String? destinationId,
    bool verifiedOnly,
  })? onGetPlaces;

  _ControllablePlaceRepo() : super(Dio());

  @override
  Future<List<PlaceModel>> getPlaces({
    int page = 1,
    int limit = 50,
    String? search,
    String? category,
    String? destinationId,
    bool verifiedOnly = true,
  }) {
    final handler = onGetPlaces;
    if (handler != null) {
      return handler(
        page: page,
        limit: limit,
        search: search,
        category: category,
        destinationId: destinationId,
        verifiedOnly: verifiedOnly,
      );
    }
    return Future.value(const []);
  }
}

HomeDestinationItem _haLongDestination({String? description}) {
  return HomeDestinationItem(
    id: 'd1111111-1111-4111-8111-111111111111',
    name: 'Hạ Long',
    nameEn: 'Ha Long',
    slug: 'ha-long',
    province: 'Quảng Ninh',
    region: 'north',
    description:
        description ?? 'Thành phố biển di sản tại tỉnh Quảng Ninh.',
    isPopular: true,
    placeCount: 24,
  );
}

PlaceModel _thapDongHoPlace() {
  return PlaceModel.fromJson({
    'id': '65562a67-84ff-44a0-990d-31917a2a9bd0',
    'name': 'Tháp Đồng Hồ',
    'address': 'Lê Thánh Tông, Bạch Đằng, Hạ Long, Quảng Ninh',
    'latitude': 20.9516105,
    'longitude': 107.0851999,
    'rating': null,
    'reviewCount': 0,
    'category': {'name': 'attraction'},
    'destination': {'name': 'Hạ Long'},
    'isVerified': true,
    'provenanceCount': 1,
  });
}

Future<void> _openSheetHost(
  WidgetTester tester, {
  required _ControllablePlaceRepo repo,
  required HomeDestinationItem destination,
}) async {
  tester.view.physicalSize = const Size(360, 640);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(() {
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
    tester.view.resetViewInsets();
  });

  await tester.pumpWidget(
    ProviderScope(
      overrides: [placeRepositoryProvider.overrideWithValue(repo)],
      child: MaterialApp(
        theme: AppTheme.lightTheme,
        home: Scaffold(
          body: Builder(
            builder: (context) => Center(
              child: ElevatedButton(
                key: const Key('open_ha_long_sheet_btn'),
                onPressed: () => showDestinationPlacesSheet(
                  context,
                  destination: destination,
                ),
                child: const Text('Mở Hạ Long'),
              ),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.pump();
  await tester.tap(find.byKey(const Key('open_ha_long_sheet_btn')));
  // Let sheet route transition finish without blocking on AppLoading spinner.
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 350));
}

void main() {
  group('GAP-18: DestinationPlacesSheet keyboard overflow safety (360x640)', () {
    testWidgets(
      'Hạ Long with description does not overflow with viewInsets.bottom = 300 in loading, populated, empty, and error states',
      (tester) async {
        final errors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          errors.add(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        Completer<List<PlaceModel>>? pendingLoad =
            Completer<List<PlaceModel>>();
        bool shouldThrow = false;
        List<PlaceModel> nextResult = [_thapDongHoPlace()];

        final repo = _ControllablePlaceRepo()
          ..onGetPlaces = ({
            page = 1,
            limit = 50,
            search,
            category,
            destinationId,
            verifiedOnly = true,
          }) {
            if (pendingLoad != null) {
              return pendingLoad.future;
            }
            if (shouldThrow) {
              return Future<List<PlaceModel>>.error(
                DioException(
                  requestOptions: RequestOptions(path: '/places'),
                  type: DioExceptionType.connectionError,
                ),
              );
            }
            if (search != null && search.isNotEmpty) {
              return Future.value(
                nextResult
                    .where((p) =>
                        p.name.toLowerCase().contains(search.toLowerCase()))
                    .toList(),
              );
            }
            return Future.value(nextResult);
          };

        // 1. Loading state with description + search bar tapped + viewInsets.bottom = 300
        await _openSheetHost(
          tester,
          repo: repo,
          destination: _haLongDestination(
            description:
                'Thành phố biển di sản tại tỉnh Quảng Ninh với vịnh Hạ Long và Tháp Đồng Hồ.',
          ),
        );
        expect(find.byType(AppLoading), findsOneWidget);

        final searchBar = find.byKey(const Key('destination_places_search_bar'));
        expect(searchBar, findsOneWidget);
        await tester.tap(searchBar);
        tester.view.viewInsets = const FakeViewPadding(bottom: 300);
        await tester.pump();

        expect(
          MediaQuery.of(tester.element(searchBar)).viewInsets.bottom,
          300,
        );
        expect(find.byType(AppLoading), findsOneWidget);
        expect(errors, isEmpty);

        // 2. Populated state while keyboard (viewInsets.bottom = 300) remains open
        final firstLoad = pendingLoad;
        pendingLoad = null;
        firstLoad.complete([_thapDongHoPlace()]);
        await tester.pumpAndSettle();

        expect(
          find.byKey(const Key('dest_place_tile_65562a67-84ff-44a0-990d-31917a2a9bd0')),
          findsOneWidget,
        );
        expect(errors, isEmpty);

        // 3. Empty state triggered via search while keyboard is open
        await tester.enterText(searchBar, 'khong-ton-tai');
        await tester.pump(const Duration(milliseconds: 350));
        await tester.pumpAndSettle();

        expect(find.byType(AppEmptyState), findsOneWidget);
        expect(errors, isEmpty);

        // 4. Error state triggered via search while keyboard is open
        shouldThrow = true;
        await tester.enterText(searchBar, 'loi-mang');
        await tester.pump(const Duration(milliseconds: 350));
        await tester.pumpAndSettle();

        expect(find.byType(AppErrorState), findsOneWidget);
        expect(errors, isEmpty);

        // 5. Closing keyboard restores description and bottom CTA
        shouldThrow = false;
        nextResult = [_thapDongHoPlace()];
        tester.view.resetViewInsets();
        await tester.pumpAndSettle();

        expect(find.text('Mở trên Bản đồ'), findsOneWidget);
        expect(
          find.textContaining('Thành phố biển di sản tại tỉnh Quảng Ninh'),
          findsOneWidget,
        );
        expect(errors, isEmpty);
      },
    );

    testWidgets(
      'Hạ Long sheet with seeded 1-line description also avoids overflow under viewInsets.bottom = 300 across retry/error flow',
      (tester) async {
        final errors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          errors.add(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        final repo = _ControllablePlaceRepo()
          ..onGetPlaces = ({
            page = 1,
            limit = 50,
            search,
            category,
            destinationId,
            verifiedOnly = true,
          }) =>
              Future<List<PlaceModel>>.error(Exception('network failure'));

        await _openSheetHost(
          tester,
          repo: repo,
          destination: _haLongDestination(),
        );
        final searchBar = find.byKey(const Key('destination_places_search_bar'));
        await tester.tap(searchBar);
        tester.view.viewInsets = const FakeViewPadding(bottom: 300);
        await tester.pumpAndSettle();

        expect(find.byType(AppErrorState), findsOneWidget);
        expect(errors, isEmpty);
      },
    );
  });
}
