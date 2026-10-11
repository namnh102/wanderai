import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:wanderai_mobile/features/trips/data/trip_models.dart';
import 'package:wanderai_mobile/features/trips/data/trip_repository.dart';
import 'package:wanderai_mobile/features/trips/providers/trip_provider.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_list_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_form_screen.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_detail_screen.dart';

class FakeTripRepository extends TripRepository {
  bool shouldFail = false;
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
  Future<void> deleteItineraryItem(String tripId, String itemId) async {}
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

      expect(find.text('Chuyen di cua toi'), findsOneWidget);
      expect(find.text('Kham pha Da Nang 3 ngay'), findsOneWidget);
      expect(find.text('Da len lich'), findsOneWidget);
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

      expect(find.text('Chua co chuyen di nao'), findsOneWidget);
      expect(find.text('Tao chuyen di moi'), findsWidgets);
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
      await tester.ensureVisible(find.text('Tao chuyen di'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Tao chuyen di'));
      await tester.pumpAndSettle();

      expect(find.text('Vui long nhap ten chuyen di'), findsOneWidget);
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
      expect(find.text('Lich trinh chi tiet'), findsOneWidget);
      expect(find.text('Ngay 1'), findsOneWidget);
      expect(find.text('Tham quan Bao tang'), findsOneWidget);
    });
  });
}
