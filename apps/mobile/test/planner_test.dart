import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:wanderai_mobile/features/trips/data/trip_models.dart';
import 'package:wanderai_mobile/features/trips/data/trip_repository.dart';
import 'package:wanderai_mobile/features/trips/providers/trip_provider.dart';
import 'package:wanderai_mobile/features/trips/presentation/trip_detail_screen.dart';

class FakePlannerTripRepository extends TripRepository {
  bool shouldFailPlan = false;
  bool shouldFailSave = false;
  bool planCalled = false;
  bool bulkSaveCalled = false;

  late TripModel currentTrip;
  late AiPlanPreviewModel fakePlan;

  FakePlannerTripRepository() : super(Dio()) {
    currentTrip = const TripModel(
      id: 'trip_ai_123',
      userId: 'user_1',
      title: 'Chuyen di Da Nang 2N',
      destinationName: 'Da Nang',
      totalBudget: 2000000,
      itineraries: [
        ItineraryModel(
          id: 'itin_old',
          tripId: 'trip_ai_123',
          dayNumber: 1,
          items: [
            ItineraryItemModel(
              id: 'item_old',
              itineraryId: 'itin_old',
              orderIndex: 1,
              activity: 'Hoat dong cu can ghi de',
            ),
          ],
        ),
      ],
    );

    fakePlan = const AiPlanPreviewModel(
      tripId: 'trip_ai_123',
      destination: 'Da Nang',
      totalDays: 2,
      overview: 'Lich trinh 2 ngay kham pha Da Nang cuc chat cung Wandy.',
      bestTimeToVisit: 'Thang 4 - Thang 8',
      budgetAnalysis: BudgetAnalysisModel(
        totalBudget: 2000000,
        estimatedCost: 1500000,
        currency: 'VND',
        isOverBudget: false,
        variance: 500000,
      ),
      days: [
        AiPlanDayModel(
          dayNumber: 1,
          title: 'Ngay 1: Bien My Khe',
          dayCost: 700000,
          items: [
            AiPlanItemModel(
              orderIndex: 1,
              activity: 'An sang mi Quang ech',
              startTime: '08:00',
              estimatedCost: 50000,
            ),
          ],
        ),
        AiPlanDayModel(
          dayNumber: 2,
          title: 'Ngay 2: Son Tra',
          dayCost: 800000,
          items: [
            AiPlanItemModel(
              orderIndex: 1,
              activity: 'Vieng Chua Linh Ung',
              startTime: '09:00',
              estimatedCost: 0,
            ),
          ],
        ),
      ],
    );
  }

  @override
  Future<TripModel> getTripDetail(String id) async {
    return currentTrip;
  }

  @override
  Future<AiPlanPreviewModel> generateAiPlan(String tripId, {String? prompt}) async {
    planCalled = true;
    if (shouldFailPlan) {
      throw DioException(
        requestOptions: RequestOptions(path: '/trips/$tripId/ai-plan'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/trips/$tripId/ai-plan'),
          statusCode: 500,
          data: {'message': 'AI Planner error'},
        ),
      );
    }
    return fakePlan;
  }

  @override
  Future<TripModel> bulkSaveItinerary(
    String tripId,
    BulkSaveItineraryRequest request,
  ) async {
    bulkSaveCalled = true;
    if (shouldFailSave) {
      throw DioException(
        requestOptions: RequestOptions(path: '/trips/$tripId/itinerary/bulk'),
        type: DioExceptionType.badResponse,
        response: Response(
          requestOptions: RequestOptions(path: '/trips/$tripId/itinerary/bulk'),
          statusCode: 500,
          data: {'message': 'Bulk save failed'},
        ),
      );
    }

    currentTrip = TripModel(
      id: tripId,
      userId: 'user_1',
      title: 'Chuyen di Da Nang 2N',
      destinationName: 'Da Nang',
      totalBudget: 2000000,
      status: 'PLANNED',
      itineraries: [
        ItineraryModel(
          id: 'itin_ai_1',
          tripId: tripId,
          dayNumber: 1,
          title: 'Ngay 1: Bien My Khe',
          items: const [
            ItineraryItemModel(
              id: 'ai_item_1',
              itineraryId: 'itin_ai_1',
              orderIndex: 1,
              activity: 'An sang mi Quang ech',
              estimatedCost: 50000,
            ),
          ],
        ),
        ItineraryModel(
          id: 'itin_ai_2',
          tripId: tripId,
          dayNumber: 2,
          title: 'Ngay 2: Son Tra',
          items: const [
            ItineraryItemModel(
              id: 'ai_item_2',
              itineraryId: 'itin_ai_2',
              orderIndex: 1,
              activity: 'Vieng Chua Linh Ung',
              estimatedCost: 0,
            ),
          ],
        ),
      ],
    );
    return currentTrip;
  }
}

void main() {
  group('AI Trip Planner Widget Tests', () {
    testWidgets('1. Renders AI Assistant card and Lap lich trinh bang AI button',
        (tester) async {
      final fakeRepo = FakePlannerTripRepository();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            tripRepositoryProvider.overrideWithValue(fakeRepo),
          ],
          child: const MaterialApp(
            home: TripDetailScreen(tripId: 'trip_ai_123'),
          ),
        ),
      );

      await tester.pumpAndSettle();

      expect(find.text('Tro ly Wandy AI'), findsOneWidget);
      expect(find.text('Lap lich trinh bang AI'), findsOneWidget);
      expect(find.byIcon(Icons.auto_awesome), findsWidgets);
    });

    testWidgets('2. Tapping AI button opens custom prompt dialog',
        (tester) async {
      final fakeRepo = FakePlannerTripRepository();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            tripRepositoryProvider.overrideWithValue(fakeRepo),
          ],
          child: const MaterialApp(
            home: TripDetailScreen(tripId: 'trip_ai_123'),
          ),
        ),
      );

      await tester.pumpAndSettle();

      final aiButton = find.text('Lap lich trinh bang AI');
      await tester.tap(aiButton);
      await tester.pumpAndSettle();

      expect(find.text('Yeu cau them (tuy chon)'), findsOneWidget);
      expect(find.text('Bat dau lap'), findsOneWidget);
      expect(find.text('Huy'), findsOneWidget);
    });

    testWidgets('3. Generates plan and displays preview modal with budget & overwrite warning',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final fakeRepo = FakePlannerTripRepository();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            tripRepositoryProvider.overrideWithValue(fakeRepo),
          ],
          child: const MaterialApp(
            home: TripDetailScreen(tripId: 'trip_ai_123'),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Tap generate button
      await tester.tap(find.text('Lap lich trinh bang AI'));
      await tester.pumpAndSettle();

      // Confirm in dialog
      await tester.tap(find.text('Bat dau lap'));
      await tester.pumpAndSettle();

      expect(fakeRepo.planCalled, isTrue);

      // Verify Modal Content
      expect(find.text('Lich trinh tu Wandy AI'), findsOneWidget);
      expect(find.text('Lich trinh 2 ngay kham pha Da Nang cuc chat cung Wandy.'), findsOneWidget);
      expect(find.text('Chi phi uoc tinh:'), findsOneWidget);
      expect(find.text('1500000 VND'), findsOneWidget);
      expect(find.text('Con du 500000 VND'), findsOneWidget);

      // Overwrite warning is visible because trip already had 1 day
      expect(
        find.text('Chuyen di da co 1 ngay. Ap dung se thay the toan bo lich trinh hien tai!'),
        findsOneWidget,
      );

      // Day titles in preview
      expect(find.text('Ngay 1: Bien My Khe'), findsOneWidget);
      expect(find.text('Ngay 2: Son Tra'), findsOneWidget);
      expect(find.text('Ap dung vao chuyen di'), findsOneWidget);
    });

    testWidgets('4. Confirming preview applies and saves bulk itinerary atomically',
        (tester) async {
      tester.view.physicalSize = const Size(800, 1400);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(() {
        tester.view.resetPhysicalSize();
        tester.view.resetDevicePixelRatio();
      });

      final fakeRepo = FakePlannerTripRepository();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            tripRepositoryProvider.overrideWithValue(fakeRepo),
          ],
          child: const MaterialApp(
            home: TripDetailScreen(tripId: 'trip_ai_123'),
          ),
        ),
      );

      await tester.pumpAndSettle();

      // Trigger generation
      await tester.tap(find.text('Lap lich trinh bang AI'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bat dau lap'));
      await tester.pumpAndSettle();

      // Tap apply button
      final applyButton = find.text('Ap dung vao chuyen di');
      expect(applyButton, findsOneWidget);
      await tester.tap(applyButton);
      await tester.pumpAndSettle();

      expect(fakeRepo.bulkSaveCalled, isTrue);
      expect(find.text('Da ap dung lich trinh AI thanh cong!'), findsOneWidget);

      // Verify that new itinerary is shown on screen
      expect(find.text('Ngay 1: Bien My Khe'), findsOneWidget);
      expect(find.text('Ngay 2: Son Tra'), findsOneWidget);
      expect(find.text('An sang mi Quang ech'), findsOneWidget);
      expect(find.text('Vieng Chua Linh Ung'), findsOneWidget);
    });

    testWidgets('5. Handles AI generation error with SnackBar notification',
        (tester) async {
      final fakeRepo = FakePlannerTripRepository();
      fakeRepo.shouldFailPlan = true;

      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            tripRepositoryProvider.overrideWithValue(fakeRepo),
          ],
          child: const MaterialApp(
            home: TripDetailScreen(tripId: 'trip_ai_123'),
          ),
        ),
      );

      await tester.pumpAndSettle();

      await tester.tap(find.text('Lap lich trinh bang AI'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bat dau lap'));
      await tester.pumpAndSettle();

      expect(find.text('AI Planner error'), findsOneWidget);
    });
  });
}
