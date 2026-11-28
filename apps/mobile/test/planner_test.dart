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

      expect(find.text('Trợ lý Wandy AI'), findsOneWidget);
      expect(find.text('Lập lịch trình bằng AI'), findsOneWidget);
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

      final aiButton = find.text('Lập lịch trình bằng AI');
      await tester.tap(aiButton);
      await tester.pumpAndSettle();

      expect(find.text('Yêu cầu thêm (tùy chọn)'), findsOneWidget);
      expect(find.text('Bắt đầu lập'), findsOneWidget);
      expect(find.text('Hủy'), findsOneWidget);
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
      await tester.tap(find.text('Lập lịch trình bằng AI'));
      await tester.pumpAndSettle();

      // Confirm in dialog
      await tester.tap(find.text('Bắt đầu lập'));
      await tester.pumpAndSettle();

      expect(fakeRepo.planCalled, isTrue);

      // Verify Modal Content
      expect(find.text('Lịch trình từ Wandy AI'), findsOneWidget);
      expect(find.text('Lich trinh 2 ngay kham pha Da Nang cuc chat cung Wandy.'), findsOneWidget);
      expect(find.text('Chi phí ước tính:'), findsOneWidget);
      expect(find.text('1500000 VND'), findsOneWidget);
      expect(find.text('Còn dư 500000 VND'), findsOneWidget);

      // Overwrite warning is visible because trip already had 1 day
      expect(
        find.text('Chuyến đi đã có 1 ngày. Áp dụng sẽ thay thế toàn bộ lịch trình hiện tại!'),
        findsOneWidget,
      );

      // Day titles in preview
      expect(find.text('Ngay 1: Bien My Khe'), findsOneWidget);
      expect(find.text('Ngay 2: Son Tra'), findsOneWidget);
      expect(find.text('Áp dụng vào chuyến đi'), findsOneWidget);
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
      await tester.tap(find.text('Lập lịch trình bằng AI'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bắt đầu lập'));
      await tester.pumpAndSettle();

      // Tap apply button
      final applyButton = find.text('Áp dụng vào chuyến đi');
      expect(applyButton, findsOneWidget);
      await tester.tap(applyButton);
      await tester.pumpAndSettle();

      expect(fakeRepo.bulkSaveCalled, isTrue);
      expect(find.text('Đã áp dụng lịch trình AI thành công!'), findsOneWidget);

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

      await tester.tap(find.text('Lập lịch trình bằng AI'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Bắt đầu lập'));
      await tester.pumpAndSettle();

      expect(find.text('AI Planner error'), findsOneWidget);
    });

    testWidgets(
      '6. Case C: Preview displays known cost, missing-price count, start-end times, and suppresses surplus when items have null price',
      (tester) async {
        tester.view.physicalSize = const Size(800, 1400);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        final fakeRepo = FakePlannerTripRepository();
        fakeRepo.fakePlan = AiPlanPreviewModel.fromJson({
          'tripId': 'trip_ai_123',
          'destination': 'Hạ Long',
          'totalDays': 1,
          'overview': 'Lịch trình có mục chưa biết giá.',
          'bestTimeToVisit': 'Quanh năm',
          'budgetAnalysis': {
            'totalBudget': 500000,
            'estimatedCost': 60000,
            'knownCostTotal': 60000,
            'unknownCostItemCount': 2,
            'costStatus': 'PARTIAL_UNKNOWN',
            'hasSufficientBudgetBasis': false,
            'currency': 'VND',
            'isOverBudget': false,
            'variance': null,
          },
          'days': [
            {
              'dayNumber': 1,
              'date': '2026-11-23',
              'title': 'Ngày 1: Hạ Long',
              'dayCost': 60000,
              'unknownCostItemCount': 2,
              'items': [
                {
                  'orderIndex': 1,
                  'startTime': '08:30',
                  'endTime': '10:00',
                  'activity': 'Cà phê tại Cafe ban mê',
                  'placeId': '70c3326e-1b53-45bf-a210-6c43a076e95b',
                  'placeName': 'Cafe ban mê',
                  'estimatedCost': null,
                  'costStatus': 'UNKNOWN',
                },
                {
                  'orderIndex': 2,
                  'startTime': '10:30',
                  'endTime': '12:00',
                  'activity': 'Tham quan Bảo tàng Quảng Ninh',
                  'placeId': '8f2b5a69-1293-4efe-8fc5-3a74193edd0f',
                  'placeName': 'Bảo tàng Quảng Ninh',
                  'estimatedCost': null,
                  'costStatus': 'UNKNOWN',
                },
                {
                  'orderIndex': 3,
                  'startTime': '14:00',
                  'endTime': '15:30',
                  'activity': 'Gửi xe & nước suối',
                  'estimatedCost': 60000,
                  'costStatus': 'KNOWN',
                },
              ],
            },
          ],
        });

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

        await tester.tap(find.text('Lập lịch trình bằng AI'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Bắt đầu lập'));
        await tester.pumpAndSettle();

        // Shows known cost + unknown item count, and NEVER claims "Còn dư ..."
        expect(find.text('Chi phí đã biết:'), findsOneWidget);
        expect(find.text('60000 VND'), findsOneWidget);
        expect(find.text('Thiếu giá: 2 mục (chưa biết)'), findsOneWidget);
        expect(find.text('Chưa đủ căn cứ tính tiền dư'), findsOneWidget);
        expect(find.textContaining('Còn dư'), findsNothing);

        // Displays BOTH startTime and endTime plus "Chưa biết giá"
        expect(find.text('08:30 - 10:00 • Chưa biết giá'), findsOneWidget);
        expect(find.text('10:30 - 12:00 • Chưa biết giá'), findsOneWidget);
        expect(find.text('14:00 - 15:30 • 60000 VND'), findsOneWidget);

        // Verify bulk payload preserves placeId and null estimatedCost
        final bulkJson = fakeRepo.fakePlan.toBulkSaveRequest().toJson();
        final bulkItems = (bulkJson['days'] as List).first['items'] as List;
        expect(bulkItems[0]['placeId'], '70c3326e-1b53-45bf-a210-6c43a076e95b');
        expect(bulkItems[0]['estimatedCost'], isNull);
      },
    );

    testWidgets(
      '7. Cases B1 & B2: Preview highlights violating items (overlap / closed POI), and rejected Apply keeps old itinerary intact with start-end times visible',
      (tester) async {
        tester.view.physicalSize = const Size(800, 1400);
        tester.view.devicePixelRatio = 1.0;
        addTearDown(() {
          tester.view.resetPhysicalSize();
          tester.view.resetDevicePixelRatio();
        });

        final fakeRepo = FakePlannerTripRepository();
        fakeRepo.currentTrip = const TripModel(
          id: 'trip_ai_123',
          userId: 'user_1',
          title: 'Chuyến đi Hạ Long',
          destinationName: 'Hạ Long',
          totalBudget: 1000000,
          itineraries: [
            ItineraryModel(
              id: 'itin_old',
              tripId: 'trip_ai_123',
              dayNumber: 1,
              title: 'Ngày 1: Lịch cũ hợp lệ',
              items: [
                ItineraryItemModel(
                  id: 'item_old',
                  itineraryId: 'itin_old',
                  orderIndex: 1,
                  startTime: '08:00',
                  endTime: '09:30',
                  activity: 'Hoạt động lịch cũ còn nguyên',
                  estimatedCost: null,
                ),
              ],
            ),
          ],
        );
        fakeRepo.shouldFailSave = true;
        fakeRepo.fakePlan = AiPlanPreviewModel.fromJson({
          'tripId': 'trip_ai_123',
          'destination': 'Hạ Long',
          'totalDays': 1,
          'overview': 'Lịch trình có chồng giờ và điểm đóng cửa.',
          'bestTimeToVisit': 'Quanh năm',
          'budgetAnalysis': {
            'totalBudget': 1000000,
            'estimatedCost': 160000,
            'knownCostTotal': 160000,
            'unknownCostItemCount': 0,
            'costStatus': 'COMPLETE',
            'hasSufficientBudgetBasis': true,
            'currency': 'VND',
            'isOverBudget': false,
            'variance': 840000,
          },
          'scheduleViolations': [
            {
              'code': 'OPENING_HOURS_CLOSED',
              'reasonCode': 'CLOSED_ON_WEEKDAY',
              'dayNumber': 1,
              'orderIndex': 2,
              'activity': 'Mua sắm tại Chợ Cái Dăm',
              'placeName': 'Chợ Cái Dăm',
              'startTime': '10:30',
              'endTime': '12:00',
              'message':
                  'Ngày 1 (2026-11-22, Chủ nhật) • Mục #2 "Chợ Cái Dăm" đóng cửa vào Chủ nhật (giờ mở cửa: Mo-Sa 08:00-16:00).',
            },
          ],
          'hasScheduleViolations': true,
          'canApply': false,
          'days': [
            {
              'dayNumber': 1,
              'date': '2026-11-22',
              'title': 'Ngày 1 (Chủ nhật)',
              'dayCost': 160000,
              'items': [
                {
                  'orderIndex': 1,
                  'startTime': '09:00',
                  'endTime': '11:00',
                  'activity': 'Cà phê sáng tại Cafe ban mê',
                  'estimatedCost': 60000,
                  'violations': [
                    {
                      'code': 'SCHEDULE_OVERLAP',
                      'reasonCode': 'OVERLAPPING_TIME_WINDOW',
                      'dayNumber': 1,
                      'orderIndex': 1,
                      'conflictingOrderIndex': 2,
                      'activity': 'Cà phê sáng tại Cafe ban mê',
                      'startTime': '09:00',
                      'endTime': '11:00',
                      'message':
                          'Chồng giờ khoảng 10:30 - 11:00 với mục #2 "Mua sắm tại Chợ Cái Dăm" (10:30 - 12:00).',
                    },
                  ],
                },
                {
                  'orderIndex': 2,
                  'startTime': '10:30',
                  'endTime': '12:00',
                  'activity': 'Mua sắm tại Chợ Cái Dăm',
                  'estimatedCost': 100000,
                  'violations': [
                    {
                      'code': 'OPENING_HOURS_CLOSED',
                      'reasonCode': 'CLOSED_ON_WEEKDAY',
                      'dayNumber': 1,
                      'orderIndex': 2,
                      'activity': 'Mua sắm tại Chợ Cái Dăm',
                      'startTime': '10:30',
                      'endTime': '12:00',
                      'message':
                          'Ngày 1 (2026-11-22, Chủ nhật) • Mục #2 "Chợ Cái Dăm" đóng cửa vào Chủ nhật (giờ mở cửa: Mo-Sa 08:00-16:00).',
                    },
                  ],
                },
              ],
            },
          ],
        });

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

        // Saved TripDetailScreen displays start-end time & unknown cost label on existing itinerary
        expect(find.text('Hoạt động lịch cũ còn nguyên'), findsOneWidget);
        expect(find.text('Thời gian: 08:00 - 09:30'), findsOneWidget);
        expect(find.text('Chi phí: Chưa biết'), findsOneWidget);

        await tester.tap(find.text('Lập lịch trình bằng AI'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Bắt đầu lập'));
        await tester.pumpAndSettle();

        // Violation banner and per-item violation cards are clearly shown in Preview
        expect(
          find.byKey(const Key('ai_plan_schedule_violations_banner')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('ai_preview_item_violation_1_1')),
          findsOneWidget,
        );
        expect(
          find.byKey(const Key('ai_preview_item_violation_1_2')),
          findsOneWidget,
        );
        expect(find.text('09:00 - 11:00 • 60000 VND'), findsOneWidget);
        expect(find.text('10:30 - 12:00 • 100000 VND'), findsOneWidget);

        // Attempting Apply gets rejected -> SnackBar shown & old itinerary remains intact!
        await tester.tap(find.text('Áp dụng vào chuyến đi'));
        await tester.pumpAndSettle();

        expect(find.byKey(const Key('trip_itinerary_error_snackbar')), findsOneWidget);
        expect(find.text('Hoạt động lịch cũ còn nguyên'), findsOneWidget);
        expect(find.text('Thời gian: 08:00 - 09:30'), findsOneWidget);
        expect(find.text('Mua sắm tại Chợ Cái Dăm'), findsNothing);
      },
    );
  });
}
