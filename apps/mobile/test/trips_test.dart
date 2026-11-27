import 'dart:async';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:wanderai_mobile/features/trips/data/trip_models.dart';
import 'package:wanderai_mobile/features/trips/data/trip_repository.dart';
import 'package:wanderai_mobile/features/trips/providers/trip_provider.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_list_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_form_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_detail_screen.dart';

class FakeTripRepository extends TripRepository {
  bool shouldFail = false;
  bool shouldFailItineraryMutation = false;
  int addItineraryCalls = 0;
  List<TripModel> memoryTrips = [];

  FakeTripRepository() : super(Dio());

  @override
  Future<List<TripModel>> getMyTrips() async {
    if (shouldFail) {
      throw DioException(
        requestOptions: RequestOptions(path: '/trips'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/trips'),
          statusCode: 500,
          data: {'message': 'Server error'},
        ),
      );
    }
    return memoryTrips;
  }

  @override
  Future<TripModel> getTripDetail(String id) async {
    if (shouldFail) {
      throw DioException(
        requestOptions: RequestOptions(path: '/trips/$id'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/trips/$id'),
          statusCode: 404,
          data: {'message': 'Chuyen di khong ton tai'},
        ),
      );
    }
    final trip = memoryTrips.firstWhere(
      (t) => t.id == id,
      orElse: () => TripModel(
        id: id,
        userId: 'user_1',
        title: 'Chuyen di mau',
        totalBudget: 3000000,
        itineraries: [
          ItineraryModel(
            id: 'itin_1',
            tripId: id,
            dayNumber: 1,
            items: [
              const ItineraryItemModel(
                id: 'item_1',
                itineraryId: 'itin_1',
                orderIndex: 1,
                activity: 'Tham quan Bao tang',
                startTime: '09:00',
                estimatedCost: 50000,
              ),
            ],
          ),
        ],
      ),
    );
    return trip;
  }

  @override
  Future<TripModel> createTrip(CreateTripRequest request) async {
    if (shouldFail) {
      throw DioException(
        requestOptions: RequestOptions(path: '/trips'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/trips'),
          statusCode: 400,
          data: {'message': 'Loi tao chuyen di'},
        ),
      );
    }
    final newTrip = TripModel(
      id: 'trip_${DateTime.now().millisecondsSinceEpoch}',
      userId: 'user_1',
      title: request.title,
      description: request.description,
      totalBudget: request.totalBudget,
      currency: request.currency ?? 'VND',
      travelStyle: request.travelStyle,
      interests: request.interests ?? [],
    );
    return newTrip;
  }

  @override
  Future<TripModel> updateTrip(String id, UpdateTripRequest request) async {
    if (shouldFail) {
      throw DioException(
        requestOptions: RequestOptions(path: '/trips/$id'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/trips/$id'),
          statusCode: 403,
          data: {'message': 'Khong co quyen sua'},
        ),
      );
    }
    final index = memoryTrips.indexWhere((t) => t.id == id);
    final old = index >= 0
        ? memoryTrips[index]
        : TripModel(id: id, userId: 'user_1', title: 'Default');

    final updated = TripModel(
      id: id,
      userId: old.userId,
      title: request.title ?? old.title,
      description: request.description ?? old.description,
      totalBudget: request.totalBudget ?? old.totalBudget,
      currency: request.currency ?? old.currency,
      travelStyle: request.travelStyle ?? old.travelStyle,
      interests: request.interests ?? old.interests,
      status: request.status ?? old.status,
      itineraries: old.itineraries,
    );
    if (index >= 0) {
      memoryTrips[index] = updated;
    }
    return updated;
  }

  @override
  Future<void> deleteTrip(String id) async {
    if (shouldFail) {
      throw DioException(
        requestOptions: RequestOptions(path: '/trips/$id'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/trips/$id'),
          statusCode: 403,
          data: {'message': 'Khong co quyen xoa'},
        ),
      );
    }
    memoryTrips.removeWhere((t) => t.id == id);
  }

  @override
  Future<ItineraryItemModel> addItineraryItem(
    String tripId,
    AddItineraryItemRequest request,
  ) async {
    addItineraryCalls++;
    if (shouldFailItineraryMutation) {
      throw DioException(
        requestOptions: RequestOptions(path: '/trips/$tripId/itinerary'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/trips/$tripId/itinerary'),
          statusCode: 400,
          data: {'message': 'Backend rejected itinerary item'},
        ),
      );
    }
    return ItineraryItemModel(
      id: 'item_${DateTime.now().millisecondsSinceEpoch}',
      itineraryId: 'itin_1',
      orderIndex: 1,
      activity: request.activity,
      startTime: request.startTime,
      estimatedCost: request.estimatedCost,
      notes: request.notes,
    );
  }

  @override
  Future<void> deleteItineraryItem(String tripId, String itemId) async {
    if (shouldFailItineraryMutation) {
      throw DioException(
        requestOptions: RequestOptions(path: '/trips/$tripId/itinerary/$itemId'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/trips/$tripId/itinerary/$itemId'),
          statusCode: 400,
          data: {'message': 'Backend rejected delete item'},
        ),
      );
    }
  }
}

class _DeferredTripRepository extends FakeTripRepository {
  Completer<AiPlanPreviewModel>? generateAiPlanCompleter;
  Completer<TripModel>? saveAiPlanCompleter;
  Completer<ItineraryItemModel>? addItineraryCompleter;
  Completer<TripModel>? createTripCompleter;
  Completer<void>? deleteTripCompleter;
  Completer<TripModel>? updateTripCompleter;
  Completer<void>? deleteItineraryCompleter;

  @override
  Future<AiPlanPreviewModel> generateAiPlan(
    String tripId, {
    String? prompt,
    AiPlanRequestOptions? options,
  }) {
    return generateAiPlanCompleter!.future;
  }

  @override
  Future<TripModel> bulkSaveItinerary(
    String tripId,
    BulkSaveItineraryRequest request, {
    String? idempotencyKey,
  }) {
    return saveAiPlanCompleter!.future;
  }

  @override
  Future<ItineraryItemModel> addItineraryItem(
    String tripId,
    AddItineraryItemRequest request,
  ) {
    return addItineraryCompleter!.future;
  }

  @override
  Future<TripModel> createTrip(CreateTripRequest request) {
    return createTripCompleter!.future;
  }

  @override
  Future<void> deleteTrip(String id) {
    return deleteTripCompleter!.future;
  }

  @override
  Future<TripModel> updateTrip(String id, UpdateTripRequest request) {
    return updateTripCompleter!.future;
  }

  @override
  Future<void> deleteItineraryItem(String tripId, String itemId) {
    return deleteItineraryCompleter!.future;
  }
}

void main() {
  group('Trip Providers & Logic (Unit Tests)', () {
    test('10. Loading state appears while fetching trips', () async {
      final fakeRepo = FakeTripRepository();
      final container = ProviderContainer(
        overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
      );

      final notifier = container.read(tripListProvider.notifier);
      final future = notifier.loadTrips();

      expect(container.read(tripListProvider).isLoading, true);
      await future;
      expect(container.read(tripListProvider).isLoading, false);
    });

    test('2. Empty trips state when user has no trips', () async {
      final fakeRepo = FakeTripRepository();
      final container = ProviderContainer(
        overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
      );

      await container.read(tripListProvider.notifier).loadTrips();
      final state = container.read(tripListProvider);

      expect(state.isEmpty, true);
      expect(state.trips, isEmpty);
    });

    test('4. Successful trip creation adds trip to list', () async {
      final fakeRepo = FakeTripRepository();
      final container = ProviderContainer(
        overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
      );

      final notifier = container.read(tripListProvider.notifier);
      final created = await notifier.createTrip(const CreateTripRequest(
        title: 'Ha Giang Tour',
        totalBudget: 4000000,
        currency: 'VND',
        travelStyle: 'COMFORT',
      ));

      expect(created, isNotNull);
      expect(created!.title, 'Ha Giang Tour');
      expect(container.read(tripListProvider).trips.length, 1);
      expect(container.read(tripListProvider).trips.first.title, 'Ha Giang Tour');
    });

    test('5. Error state captures server error message', () async {
      final fakeRepo = FakeTripRepository()..shouldFail = true;
      final container = ProviderContainer(
        overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
      );

      await container.read(tripListProvider.notifier).loadTrips();
      final state = container.read(tripListProvider);

      expect(state.errorMessage, isNotNull);
      expect(state.trips, isEmpty);
    });

    test('7. Edit trip updates trip in detail state', () async {
      final fakeRepo = FakeTripRepository();
      final container = ProviderContainer(
        overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
      );

      final detailNotifier = container.read(tripDetailProvider.notifier);
      await detailNotifier.loadTrip('trip_1');
      expect(container.read(tripDetailProvider).trip?.title, 'Chuyen di mau');

      final success = await detailNotifier.updateTrip(
        'trip_1',
        const UpdateTripRequest(title: 'Tieu de moi da cap nhat'),
      );

      expect(success, true);
      expect(
        container.read(tripDetailProvider).trip?.title,
        'Tieu de moi da cap nhat',
      );
    });

    test('8. Delete trip removes trip from list', () async {
      final fakeRepo = FakeTripRepository();
      final container = ProviderContainer(
        overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
      );

      final listNotifier = container.read(tripListProvider.notifier);
      final trip = await listNotifier.createTrip(const CreateTripRequest(
        title: 'Chuyen sap xoa',
      ));
      expect(container.read(tripListProvider).trips.length, 1);

      final ok = await listNotifier.deleteTrip(trip!.id);
      expect(ok, true);
      expect(container.read(tripListProvider).trips, isEmpty);
    });

    test('TripContext converts correctly from TripModel', () {
      const trip = TripModel(
        id: 't_1',
        userId: 'u_1',
        title: 'Ha Giang',
        destinationName: 'Ha Giang',
        totalBudget: 3500000,
        currency: 'VND',
        travelStyle: 'COMFORT',
        interests: ['nature', 'food'],
      );

      final context = trip.toTripContext();
      expect(context.tripId, 't_1');
      expect(context.destination, 'Ha Giang');
      expect(context.budget, 3500000);
      expect(context.travelStyle, 'COMFORT');
      expect(context.interests, contains('nature'));
      expect(context.toJson()['currency'], 'VND');
    });

    test(
      'GAP-16: disposing TripDetailNotifier and TripListNotifier mid-flight throws zero StateErrors on resolve or reject',
      () async {
        const sampleTrip = TripModel(
          id: 'trip_1',
          userId: 'user_1',
          title: 'Hạ Long 2N1Đ',
        );
        const samplePlan = AiPlanPreviewModel(
          tripId: 'trip_1',
          destination: 'Hạ Long',
          totalDays: 1,
          overview: 'Tổng quan',
          bestTimeToVisit: 'Mùa thu',
          budgetAnalysis: BudgetAnalysisModel(),
        );
        const sampleItem = ItineraryItemModel(
          id: 'item_1',
          itineraryId: 'itin_1',
          orderIndex: 1,
          activity: 'Tháp Đồng Hồ',
        );
        DioException makeDioError(String path) => DioException(
              requestOptions: RequestOptions(path: path),
              type: DioExceptionType.connectionError,
            );

        for (final shouldReject in [false, true]) {
          final repo = _DeferredTripRepository()
            ..generateAiPlanCompleter = Completer<AiPlanPreviewModel>()
            ..saveAiPlanCompleter = Completer<TripModel>()
            ..addItineraryCompleter = Completer<ItineraryItemModel>()
            ..updateTripCompleter = Completer<TripModel>()
            ..deleteItineraryCompleter = Completer<void>()
            ..createTripCompleter = Completer<TripModel>()
            ..deleteTripCompleter = Completer<void>();

          final detailNotifier = TripDetailNotifier(repo);
          final listNotifier = TripListNotifier(repo);
          // Let initial loadTrips settle before starting in-flight mutations.
          await Future<void>.delayed(Duration.zero);

          final genFuture = detailNotifier.generateAiPlan('trip_1');
          final saveFuture = detailNotifier.saveAiPlan('trip_1', samplePlan);
          final addItemFuture = detailNotifier.addItineraryItem(
            'trip_1',
            const AddItineraryItemRequest(dayNumber: 1, activity: 'Tháp Đồng Hồ'),
          );
          final updateFuture = detailNotifier.updateTrip(
            'trip_1',
            const UpdateTripRequest(title: 'Updated'),
          );
          final delItemFuture = detailNotifier.deleteItineraryItem('trip_1', 'item_1');
          final createFuture = listNotifier.createTrip(
            const CreateTripRequest(title: 'Hạ Long'),
          );
          final deleteFuture = listNotifier.deleteTrip('trip_1');

          detailNotifier.dispose();
          listNotifier.dispose();

          if (shouldReject) {
            repo.generateAiPlanCompleter!.completeError(makeDioError('/ai-plan'));
            repo.saveAiPlanCompleter!.completeError(makeDioError('/bulk'));
            repo.addItineraryCompleter!.completeError(makeDioError('/itinerary'));
            repo.updateTripCompleter!.completeError(makeDioError('/trips/trip_1'));
            repo.deleteItineraryCompleter!.completeError(makeDioError('/itinerary/item_1'));
            repo.createTripCompleter!.completeError(makeDioError('/trips'));
            repo.deleteTripCompleter!.completeError(makeDioError('/trips/trip_1'));
          } else {
            repo.generateAiPlanCompleter!.complete(samplePlan);
            repo.saveAiPlanCompleter!.complete(sampleTrip);
            repo.addItineraryCompleter!.complete(sampleItem);
            repo.updateTripCompleter!.complete(sampleTrip);
            repo.deleteItineraryCompleter!.complete();
            repo.createTripCompleter!.complete(sampleTrip);
            repo.deleteTripCompleter!.complete();
          }

          expect(await genFuture, isNull);
          expect(await saveFuture, isFalse);
          expect(await addItemFuture, isFalse);
          expect(await updateFuture, isFalse);
          expect(await delItemFuture, isFalse);
          expect(await createFuture, isNull);
          expect(await deleteFuture, isFalse);
        }
      },
    );
  });

  group('Trip Widgets Tests', () {
    testWidgets('1. Trip list renders cards when trips exist', (tester) async {
      final fakeRepo = FakeTripRepository();
      fakeRepo.memoryTrips = [
        const TripModel(
          id: 't_1',
          userId: 'u_1',
          title: 'Kham pha Da Nang 3 ngay',
          totalBudget: 2500000,
          currency: 'VND',
          status: 'PLANNED',
        ),
      ];

      await tester.pumpWidget(
        ProviderScope(
          overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
          child: const MaterialApp(home: TripListScreen()),
        ),
      );
      await tester.pump();
      await tester.pumpAndSettle();

      expect(find.text('Chuyến đi của tôi'), findsOneWidget);
      expect(find.text('Kham pha Da Nang 3 ngay'), findsOneWidget);
      expect(find.text('Đã lên lịch'), findsOneWidget);
    });

    testWidgets('2. Empty trips state renders illustration and create button', (tester) async {
      final fakeRepo = FakeTripRepository();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
          child: const MaterialApp(home: TripListScreen()),
        ),
      );
      await tester.pump();
      await tester.pumpAndSettle();

      expect(find.text('Chưa có chuyến đi nào'), findsOneWidget);
      expect(find.text('Tạo chuyến đi mới'), findsWidgets);
    });

    testWidgets('3. Create trip validation rejects empty title', (tester) async {
      final fakeRepo = FakeTripRepository();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
          child: const MaterialApp(home: TripFormScreen()),
        ),
      );
      await tester.pump();

      // Ensure submit button is scrolled into view before tapping
      await tester.ensureVisible(find.text('Tạo chuyến đi'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Tạo chuyến đi'));
      await tester.pumpAndSettle();

      expect(find.text('Vui lòng nhập tên chuyến đi'), findsOneWidget);
    });

    testWidgets('6 & 9. Trip detail renders overview and itinerary', (tester) async {
      final fakeRepo = FakeTripRepository();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
          child: const MaterialApp(home: TripDetailScreen(tripId: 'trip_1')),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pumpAndSettle();

      expect(find.text('Chuyen di mau'), findsWidgets);
      expect(find.text('Lịch trình chi tiết'), findsOneWidget);
      expect(find.text('Ngày 1'), findsOneWidget);
      expect(find.text('Tham quan Bao tang'), findsOneWidget);
    });

    testWidgets('GAP-10: TripDetailScreen validates cost before popping, shows SnackBar on add/delete failure, and guards delete with canPop', (tester) async {
      final fakeRepo = FakeTripRepository()..shouldFailItineraryMutation = true;

      final router = GoRouter(
        initialLocation: '/trips/trip_1',
        routes: [
          GoRoute(
            path: '/trips',
            builder: (_, __) => const TripListScreen(),
          ),
          GoRoute(
            path: '/trips/:id',
            builder: (_, state) => TripDetailScreen(
              tripId: state.pathParameters['id']!,
            ),
          ),
        ],
      );

      await tester.pumpWidget(
        ProviderScope(
          overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
          child: MaterialApp.router(routerConfig: router),
        ),
      );
      await tester.pump();
      await tester.pumpAndSettle();

      // 1. Open Add Itinerary dialog & reject negative cost inside dialog
      final addBtn = find.text('Thêm hoạt động');
      await tester.ensureVisible(addBtn.first);
      await tester.tap(addBtn.first);
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('trip_add_item_activity_input')),
        'Tháp Đồng Hồ',
      );
      await tester.enterText(
        find.byKey(const Key('trip_add_item_cost_input')),
        '-5000',
      );
      await tester.tap(find.byKey(const Key('trip_add_item_submit_button')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('trip_add_item_dialog_error')), findsOneWidget);
      expect(fakeRepo.addItineraryCalls, 0);

      // 2. Fix cost to valid non-negative integer -> submits and shows SnackBar on backend failure
      await tester.enterText(
        find.byKey(const Key('trip_add_item_cost_input')),
        '50000',
      );
      await tester.tap(find.byKey(const Key('trip_add_item_submit_button')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(fakeRepo.addItineraryCalls, 1);
      expect(find.byKey(const Key('trip_itinerary_error_snackbar')), findsOneWidget);
      expect(find.textContaining('Backend rejected itinerary item'), findsOneWidget);

      // Clear SnackBar before testing delete failure
      ScaffoldMessenger.of(tester.element(find.byType(TripDetailScreen)))
          .clearSnackBars();
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // 3. Delete itinerary item failure shows SnackBar even when trip != null
      final deleteItemBtn = find.byTooltip('Xóa hoạt động').first;
      await tester.ensureVisible(deleteItemBtn);
      await tester.tap(deleteItemBtn);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      expect(find.byKey(const Key('trip_itinerary_error_snackbar')), findsOneWidget);
      expect(find.textContaining('Backend rejected delete item'), findsOneWidget);

      ScaffoldMessenger.of(tester.element(find.byType(TripDetailScreen)))
          .clearSnackBars();
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));

      // 4. Delete entire trip when canPop() is false navigates to /trips cleanly
      await tester.tap(find.byTooltip('Xóa chuyến đi'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 300));
      await tester.tap(find.text('Xóa').last);
      await tester.pumpAndSettle();

      expect(find.byType(TripListScreen), findsOneWidget);
    });

    testWidgets(
      'GAP-14: opening and canceling _handleGenerateAiPlan dialog with focused input produces zero FlutterErrors',
      (tester) async {
        final errors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          errors.add(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        final fakeRepo = FakeTripRepository();

        await tester.pumpWidget(
          ProviderScope(
            overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
            child: const MaterialApp(
              home: TripDetailScreen(tripId: 'trip_1'),
            ),
          ),
        );
        await tester.pump();
        await tester.pumpAndSettle();

        final aiBtn = find.text('Lập lịch trình bằng AI');
        await tester.ensureVisible(aiBtn);
        await tester.tap(aiBtn);
        await tester.pumpAndSettle();

        final promptInput = find.byKey(const Key('trip_ai_plan_prompt_input'));
        expect(promptInput, findsOneWidget);
        await tester.tap(promptInput);
        await tester.enterText(promptInput, 'Ưu tiên hải sản Hạ Long');
        await tester.pump();

        await tester.tap(find.byKey(const Key('trip_ai_plan_cancel_button')));
        await tester.pump(const Duration(milliseconds: 50));
        await tester.pumpAndSettle();

        expect(errors, isEmpty);
      },
    );

    testWidgets(
      'GAP-15: _AddItinerarySheet on 360x640 with viewInsets bottom 300, focused input, and validation error produces zero FlutterErrors',
      (tester) async {
        final errors = <FlutterErrorDetails>[];
        final prevOnError = FlutterError.onError;
        FlutterError.onError = (details) {
          errors.add(details);
        };
        addTearDown(() => FlutterError.onError = prevOnError);

        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
          tester.view.resetViewInsets();
        });

        final fakeRepo = FakeTripRepository();

        await tester.pumpWidget(
          ProviderScope(
            overrides: [tripRepositoryProvider.overrideWithValue(fakeRepo)],
            child: const MaterialApp(
              home: TripDetailScreen(tripId: 'trip_1'),
            ),
          ),
        );
        await tester.pump();
        await tester.pumpAndSettle();

        final addBtn = find.text('Thêm hoạt động');
        await tester.ensureVisible(addBtn.first);
        await tester.tap(addBtn.first);
        await tester.pumpAndSettle();

        final activityInput =
            find.byKey(const Key('trip_add_item_activity_input'));
        expect(activityInput, findsOneWidget);

        // Focus activity input and simulate soft keyboard opening (viewInsets.bottom = 300)
        await tester.tap(activityInput);
        tester.view.viewInsets = const FakeViewPadding(bottom: 300);
        await tester.pumpAndSettle();

        expect(
          MediaQuery.of(tester.element(activityInput)).viewInsets.bottom,
          300,
        );

        // Trigger validation error (_dialogError != null) while keyboard viewInsets is open
        final submitBtn = find.byKey(const Key('trip_add_item_submit_button'));
        await tester.ensureVisible(submitBtn);
        await tester.tap(submitBtn);
        await tester.pumpAndSettle();

        FlutterError.onError = prevOnError;
        expect(
          find.byKey(const Key('trip_add_item_dialog_error')),
          findsOneWidget,
        );
        expect(errors, isEmpty);
      },
    );
  });
}
