import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_error_state.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/app_text_field.dart';
import '../data/trip_models.dart';
import '../providers/trip_provider.dart';
import 'trip_form_screen.dart';

sealed class _SliverItineraryEntry {
  const _SliverItineraryEntry();
}

class _DayHeaderEntry extends _SliverItineraryEntry {
  final ItineraryModel day;
  const _DayHeaderEntry(this.day);
}

class _EmptyDayEntry extends _SliverItineraryEntry {
  final ItineraryModel day;
  const _EmptyDayEntry(this.day);
}

class _DayItemEntry extends _SliverItineraryEntry {
  final ItineraryItemModel item;
  final bool isLastInDay;
  const _DayItemEntry(this.item, {required this.isLastInDay});
}

class TripDetailScreen extends ConsumerStatefulWidget {
  final String tripId;

  const TripDetailScreen({super.key, required this.tripId});

  @override
  ConsumerState<TripDetailScreen> createState() => _TripDetailScreenState();
}

class _TripDetailScreenState extends ConsumerState<TripDetailScreen> {
  bool _isReordering = false;
  List<ItineraryModel> _draftItineraries = const [];

  @override
  void initState() {
    super.initState();
    Future.microtask(() async {
      await ref.read(tripDetailProvider.notifier).loadTrip(widget.tripId);
      if (!mounted) return;
      final loaded = ref.read(tripDetailProvider).trip;
      if (kDebugMode && loaded != null) {
        final orderedItems = loaded.itineraries
            .expand((d) => d.items)
            .map((i) => '${i.orderIndex}:${i.placeName ?? i.activity}')
            .toList();
        final placeIds = loaded.itineraries
            .expand((d) => d.items)
            .map((i) => i.placeId)
            .whereType<String>()
            .toList();
        debugPrint(
          '[GoMate][TripDetail] opened trip_id=${loaded.id} '
          'title="${loaded.title}" place_ids=$placeIds '
          'ordered_items=$orderedItems',
        );
      }
    });
  }

  void _enterReorderMode(TripModel trip) {
    setState(() {
      _isReordering = true;
      _draftItineraries = trip.itineraries
          .map(
            (day) => day.copyWith(
              items: List<ItineraryItemModel>.from(day.items),
            ),
          )
          .toList();
    });
  }

  void _cancelReorderMode() {
    setState(() {
      _isReordering = false;
      _draftItineraries = const [];
    });
  }

  void _handleDraftDayReorder(int dayNumber, int oldIndex, int newIndex) {
    setState(() {
      _draftItineraries = _draftItineraries.map((day) {
        if (day.dayNumber != dayNumber) return day;
        final mutable = List<ItineraryItemModel>.from(day.items);
        if (oldIndex < 0 ||
            oldIndex >= mutable.length ||
            newIndex < 0 ||
            newIndex >= mutable.length) {
          return day;
        }
        final moved = mutable.removeAt(oldIndex);
        mutable.insert(newIndex, moved);
        final reindexed = [
          for (var i = 0; i < mutable.length; i++)
            mutable[i].copyWith(orderIndex: i + 1),
        ];
        if (kDebugMode) {
          final draftSummary = reindexed
              .map((i) => '${i.orderIndex}:${i.placeName ?? i.activity}')
              .toList();
          debugPrint(
            '[GoMate][TripDetail] draft_reorder trip_id=${widget.tripId} '
            'day=$dayNumber order=$draftSummary',
          );
        }
        return day.copyWith(items: reindexed);
      }).toList();
    });
  }

  Future<void> _saveReorderedItinerary() async {
    final entries = <ReorderItineraryItemEntry>[];
    for (final day in _draftItineraries) {
      for (var i = 0; i < day.items.length; i++) {
        entries.add(
          ReorderItineraryItemEntry(
            itemId: day.items[i].id,
            orderIndex: i + 1,
          ),
        );
      }
    }
    if (entries.isEmpty) {
      _cancelReorderMode();
      return;
    }

    final ok =
        await ref.read(tripDetailProvider.notifier).reorderItineraryItems(
              widget.tripId,
              ReorderItineraryRequest(items: entries),
            );
    if (!mounted) return;

    if (ok) {
      final updated = ref.read(tripDetailProvider).trip;
      if (kDebugMode && updated != null) {
        final orderedItems = updated.itineraries
            .expand((d) => d.items)
            .map((i) => '${i.orderIndex}:${i.placeName ?? i.activity}')
            .toList();
        final placeIds = updated.itineraries
            .expand((d) => d.items)
            .map((i) => i.placeId)
            .whereType<String>()
            .toList();
        debugPrint(
          '[GoMate][TripDetail] saved_reorder trip_id=${updated.id} '
          'place_ids=$placeIds ordered_items=$orderedItems',
        );
      }
      setState(() {
        _isReordering = false;
        _draftItineraries = const [];
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          key: Key('trip_itinerary_reorder_saved_snackbar'),
          content: Text('Đã lưu thứ tự lịch trình'),
        ),
      );
    } else {
      final err = ref.read(tripDetailProvider).errorMessage ??
          'Không thể lưu thứ tự lịch trình';
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          key: const Key('trip_itinerary_error_snackbar'),
          content: Text(err),
        ),
      );
    }
  }

  Future<void> _handleDelete() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Xác nhận xóa'),
        content: const Text('Bạn có chắc chắn muốn xóa chuyến đi này không?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Hủy'),
          ),
          AppButton(
            text: 'Xóa',
            variant: AppButtonVariant.danger,
            isFullWidth: false,
            onPressed: () => Navigator.pop(ctx, true),
          ),
        ],
      ),
    );

    if (confirm == true && mounted) {
      final success =
          await ref.read(tripListProvider.notifier).deleteTrip(widget.tripId);
      if (mounted) {
        if (success) {
          if (context.canPop()) {
            context.pop();
          } else {
            context.go('/trips');
          }
        } else {
          final err =
              ref.read(tripListProvider).errorMessage ?? 'Lỗi xóa chuyến đi';
          ScaffoldMessenger.of(context)
              .showSnackBar(SnackBar(content: Text(err)));
        }
      }
    }
  }

  Future<void> _handleGenerateAiPlan() async {
    final prompt = await showDialog<String>(
      context: context,
      builder: (_) => const _AiPlanPromptDialog(),
    );

    if (prompt == null || !mounted) return;

    final plan = await ref.read(tripDetailProvider.notifier).generateAiPlan(
          widget.tripId,
          prompt: prompt.isNotEmpty ? prompt : null,
        );

    if (!mounted) return;
    if (plan != null) {
      _showAiPlanPreviewModal(plan);
    } else {
      final err = ref.read(tripDetailProvider).planErrorMessage ??
          'Không thể tạo lịch trình từ AI';
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(err)));
    }
  }

  void _showAiPlanPreviewModal(AiPlanPreviewModel plan) {
    final cs = Theme.of(context).colorScheme;
    final trip = ref.read(tripDetailProvider).trip;
    final hasExistingItinerary = trip != null && trip.itineraries.isNotEmpty;

    final unknownCostCount = plan.budgetAnalysis.unknownCostItemCount > 0
        ? plan.budgetAnalysis.unknownCostItemCount
        : plan.days.fold<int>(
            0,
            (acc, d) => acc + d.effectiveUnknownCostCount,
          );
    final hasUnknownCosts = unknownCostCount > 0;
    final canShowSurplus = !hasUnknownCosts &&
        plan.budgetAnalysis.hasSufficientBudgetBasis &&
        plan.budgetAnalysis.variance != null &&
        !plan.budgetAnalysis.isOverBudget;
    final overBudgetAmount = plan.budgetAnalysis.variance != null
        ? -plan.budgetAnalysis.variance!
        : ((plan.budgetAnalysis.totalBudget ?? 0) -
                plan.budgetAnalysis.knownCostTotal)
            .abs();

    final summaryViolations = plan.scheduleViolations.isNotEmpty
        ? plan.scheduleViolations
        : plan.days
            .expand((d) => d.items.expand((item) => item.violations))
            .toList();

    final previewEntries = <Widget>[
      if (plan.overview.isNotEmpty)
        Container(
          padding: const EdgeInsets.all(12),
          margin: const EdgeInsets.only(bottom: 12),
          decoration: BoxDecoration(
            color: cs.surfaceContainerLow,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            plan.overview,
            style: TextStyle(fontSize: 13, color: cs.onSurface),
          ),
        ),
      Container(
        key: const Key('ai_plan_budget_summary_card'),
        padding: const EdgeInsets.all(12),
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: plan.budgetAnalysis.isOverBudget
              ? cs.errorContainer.withValues(alpha: 0.3)
              : cs.primaryContainer.withValues(alpha: 0.2),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: plan.budgetAnalysis.isOverBudget ? cs.error : cs.primary,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    hasUnknownCosts ? 'Chi phí đã biết:' : 'Chi phí ước tính:',
                    style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
                  ),
                  Text(
                    '${hasUnknownCosts ? plan.budgetAnalysis.knownCostTotal : plan.budgetAnalysis.estimatedCost} ${plan.budgetAnalysis.currency}',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: plan.budgetAnalysis.isOverBudget
                          ? cs.error
                          : cs.primary,
                    ),
                  ),
                  if (hasUnknownCosts) ...[
                    const SizedBox(height: 4),
                    Text(
                      'Thiếu giá: $unknownCostCount mục (chưa biết)',
                      key: const Key('ai_plan_unknown_cost_count_text'),
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Colors.orange.shade900,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            if (plan.budgetAnalysis.totalBudget != null) ...[
              const SizedBox(width: 8),
              Flexible(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      'Ngân sách: ${plan.budgetAnalysis.totalBudget} ${plan.budgetAnalysis.currency}',
                      textAlign: TextAlign.end,
                      style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
                    ),
                    Text(
                      plan.budgetAnalysis.isOverBudget
                          ? (hasUnknownCosts
                              ? 'Vượt ít nhất $overBudgetAmount VND'
                              : 'Vượt $overBudgetAmount VND')
                          : (canShowSurplus
                              ? 'Còn dư ${plan.budgetAnalysis.variance} VND'
                              : 'Chưa đủ căn cứ tính tiền dư'),
                      key: const Key('ai_plan_budget_status_text'),
                      textAlign: TextAlign.end,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: plan.budgetAnalysis.isOverBudget
                            ? cs.error
                            : (canShowSurplus
                                ? cs.primary
                                : cs.onSurfaceVariant),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
      if (summaryViolations.isNotEmpty)
        Container(
          key: const Key('ai_plan_schedule_violations_banner'),
          padding: const EdgeInsets.all(12),
          margin: const EdgeInsets.only(bottom: 12),
          decoration: BoxDecoration(
            color: cs.errorContainer.withValues(alpha: 0.35),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: cs.error),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.error_outline, color: cs.error, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Phát hiện ${summaryViolations.length} vi phạm thời gian / giờ mở cửa',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                        color: cs.error,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              ...summaryViolations.map(
                (v) => Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Text(
                    '• ${v.message}',
                    style: TextStyle(fontSize: 12, color: cs.onSurface),
                  ),
                ),
              ),
              const SizedBox(height: 2),
              Text(
                'Yêu cầu áp dụng sẽ bị từ chối theo quy tắc bảo vệ lịch trình và giữ nguyên lịch cũ.',
                style: TextStyle(
                  fontSize: 11,
                  fontStyle: FontStyle.italic,
                  color: cs.error,
                ),
              ),
            ],
          ),
        ),
      if (hasExistingItinerary)
        Container(
          padding: const EdgeInsets.all(12),
          margin: const EdgeInsets.only(bottom: 16),
          decoration: BoxDecoration(
            color: Colors.amber.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.amber.shade700),
          ),
          child: Row(
            children: [
              Icon(Icons.warning_amber_rounded,
                  color: Colors.amber.shade900, size: 20),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Chuyến đi đã có ${trip.itineraries.length} ngày. Áp dụng sẽ thay thế toàn bộ lịch trình hiện tại!',
                  style: TextStyle(fontSize: 12, color: Colors.amber.shade900),
                ),
              ),
            ],
          ),
        ),
    ];

    final totalCount = previewEntries.length + plan.days.length;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.85,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        expand: false,
        builder: (ctx, scrollCtrl) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Column(
            children: [
              const SizedBox(height: 12),
              Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: cs.outlineVariant,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.auto_awesome,
                                color: cs.primary, size: 20),
                            const SizedBox(width: 8),
                            const Expanded(
                              child: Text(
                                'Lịch trình từ Wandy AI',
                                style: TextStyle(
                                    fontSize: 18, fontWeight: FontWeight.bold),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(
                          '${plan.destination} • ${plan.totalDays} ngày',
                          style: TextStyle(
                              fontSize: 13, color: cs.onSurfaceVariant),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(ctx),
                  ),
                ],
              ),
              const Divider(),
              Expanded(
                child: ListView.builder(
                  controller: scrollCtrl,
                  padding: const EdgeInsets.only(bottom: 20),
                  itemCount: totalCount,
                  itemBuilder: (_, index) {
                    if (index < previewEntries.length) {
                      return previewEntries[index];
                    }
                    final day = plan.days[index - previewEntries.length];
                    return _buildAiPreviewDayCard(day, cs);
                  },
                ),
              ),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Row(
                    children: [
                      Expanded(
                        child: AppButton(
                          text: 'Hủy',
                          variant: AppButtonVariant.secondary,
                          onPressed: () => Navigator.pop(ctx),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        flex: 2,
                        child: AppButton(
                          text: 'Áp dụng vào chuyến đi',
                          icon: Icons.check,
                          onPressed: () async {
                            Navigator.pop(ctx);
                            final success = await ref
                                .read(tripDetailProvider.notifier)
                                .saveAiPlan(widget.tripId, plan,
                                    replaceExisting: true);
                            if (mounted) {
                              if (success) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text(
                                        'Đã áp dụng lịch trình AI thành công!'),
                                  ),
                                );
                              } else {
                                final err =
                                    ref.read(tripDetailProvider).errorMessage ??
                                        'Lỗi khi lưu lịch trình';
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    key: const Key(
                                        'trip_itinerary_error_snackbar'),
                                    content: Text(err),
                                  ),
                                );
                              }
                            }
                          },
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAiPreviewDayCard(AiPlanDayModel day, ColorScheme cs) {
    final dayUnknownCount = day.effectiveUnknownCostCount;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: cs.outlineVariant.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  day.title,
                  style: const TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 14),
                ),
              ),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  dayUnknownCount > 0
                      ? 'Đã biết: ${day.dayCost} VND • $dayUnknownCount mục chưa biết'
                      : '${day.dayCost} VND',
                  textAlign: TextAlign.end,
                  style: TextStyle(
                      fontSize: 12,
                      color: cs.primary,
                      fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const Divider(height: 16),
          ...day.items.map((item) {
            final hasViolation = item.violations.isNotEmpty;
            final timeRange =
                formatItineraryTimeRange(item.startTime, item.endTime);
            final costLabel = item.estimatedCost != null
                ? '${item.estimatedCost} VND'
                : 'Chưa biết giá';
            final metaLabel =
                timeRange != null ? '$timeRange • $costLabel' : costLabel;

            return Container(
              key: hasViolation
                  ? Key(
                      'ai_preview_item_violation_${day.dayNumber}_${item.orderIndex}')
                  : null,
              margin: const EdgeInsets.symmetric(vertical: 4),
              padding: hasViolation
                  ? const EdgeInsets.all(8)
                  : const EdgeInsets.symmetric(vertical: 2),
              decoration: hasViolation
                  ? BoxDecoration(
                      color: cs.errorContainer.withValues(alpha: 0.25),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: cs.error),
                    )
                  : null,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${item.orderIndex}. ',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: hasViolation ? cs.error : cs.primary,
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            if (hasViolation) ...[
                              Icon(Icons.warning_amber_rounded,
                                  size: 15, color: cs.error),
                              const SizedBox(width: 4),
                            ],
                            Expanded(
                              child: Text(
                                item.activity,
                                style: TextStyle(
                                  fontWeight: FontWeight.w600,
                                  fontSize: 13,
                                  color: hasViolation ? cs.error : null,
                                ),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 2),
                        Text(
                          metaLabel,
                          style: TextStyle(
                            fontSize: 11,
                            color: item.estimatedCost == null
                                ? Colors.orange.shade900
                                : cs.onSurfaceVariant,
                          ),
                        ),
                        if (hasViolation) ...[
                          const SizedBox(height: 4),
                          ...item.violations.map(
                            (v) => Text(
                              v.message,
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: cs.error,
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  void _showAddItineraryDialog(int defaultDay) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => _AddItinerarySheet(
        defaultDay: defaultDay,
        onSubmit: (request) async {
          final ok = await ref
              .read(tripDetailProvider.notifier)
              .addItineraryItem(widget.tripId, request);
          if (!ok && mounted) {
            final err = ref.read(tripDetailProvider).errorMessage ??
                'Không thể thêm hoạt động vào lịch trình';
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                key: const Key('trip_itinerary_error_snackbar'),
                content: Text(err),
              ),
            );
          }
        },
      ),
    );
  }

  List<_SliverItineraryEntry> _flattenItineraries(List<ItineraryModel> days) {
    final entries = <_SliverItineraryEntry>[];
    for (final day in days) {
      entries.add(_DayHeaderEntry(day));
      if (day.items.isEmpty) {
        entries.add(_EmptyDayEntry(day));
      } else {
        for (var i = 0; i < day.items.length; i++) {
          entries.add(
            _DayItemEntry(
              day.items[i],
              isLastInDay: i == day.items.length - 1,
            ),
          );
        }
      }
    }
    return entries;
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(tripDetailProvider);
    final cs = Theme.of(context).colorScheme;

    if (state.trip == null) {
      if (state.errorMessage != null) {
        return Scaffold(
          appBar: AppBar(),
          body: AppErrorState(
            message: state.errorMessage!,
            onRetry: () =>
                ref.read(tripDetailProvider.notifier).loadTrip(widget.tripId),
          ),
        );
      }
      return const Scaffold(
        body: AppLoading(message: 'Đang tải chi tiết chuyến đi...'),
      );
    }

    final trip = state.trip!;
    final entries = _flattenItineraries(trip.itineraries);

    return Scaffold(
      appBar: AppBar(
        title: Text(
          trip.title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        actions: [
          IconButton(
            key: const Key('trip_detail_open_groups_button'),
            icon: const Icon(Icons.groups_outlined),
            tooltip: 'Nhóm đồng hành',
            onPressed: () => context.push('/groups?tripId=${trip.id}'),
          ),
          IconButton(
            icon: const Icon(Icons.edit_outlined),
            tooltip: 'Chỉnh sửa',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => TripFormScreen(existingTrip: trip),
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline),
            tooltip: 'Xóa chuyến đi',
            onPressed: _handleDelete,
          ),
        ],
      ),
      body: CustomScrollView(
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              AppSpacing.md,
              AppSpacing.md,
              AppSpacing.sm,
            ),
            sliver: SliverToBoxAdapter(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Overview Card
                  Card(
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                      side: BorderSide(
                          color: cs.outlineVariant.withValues(alpha: 0.6)),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            trip.title,
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          if (trip.description != null &&
                              trip.description!.isNotEmpty) ...[
                            const SizedBox(height: 8),
                            Text(
                              trip.description!,
                              style: TextStyle(
                                  fontSize: 14, color: cs.onSurfaceVariant),
                            ),
                          ],
                          const Divider(height: 24),
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                child: _buildInfoColumn(
                                  'Ngân sách',
                                  trip.totalBudget != null
                                      ? '${trip.totalBudget} ${trip.currency}'
                                      : 'Chưa đặt',
                                  Icons.payments_outlined,
                                  cs,
                                ),
                              ),
                              Expanded(
                                child: _buildInfoColumn(
                                  'Thời gian',
                                  trip.startDate != null
                                      ? '${trip.startDate!.day}/${trip.startDate!.month}'
                                      : 'Chưa chọn',
                                  Icons.calendar_today_outlined,
                                  cs,
                                ),
                              ),
                              Expanded(
                                child: _buildInfoColumn(
                                  'Phong cách',
                                  trip.travelStyle ?? 'Tự do',
                                  Icons.explore_outlined,
                                  cs,
                                ),
                              ),
                            ],
                          ),
                          if (trip.interests.isNotEmpty) ...[
                            const SizedBox(height: 12),
                            Wrap(
                              spacing: 6,
                              children: trip.interests
                                  .map((tag) => Chip(
                                        label: Text(tag,
                                            style:
                                                const TextStyle(fontSize: 11)),
                                        visualDensity: VisualDensity.compact,
                                      ))
                                  .toList(),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // AI Planning Action Card
                  Card(
                    elevation: 0,
                    color: cs.primaryContainer.withValues(alpha: 0.15),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                      side:
                          BorderSide(color: cs.primary.withValues(alpha: 0.3)),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(Icons.auto_awesome,
                                  color: cs.primary, size: 20),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  'Trợ lý Wandy AI',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 15,
                                    color: cs.primary,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'Wandy sẽ tự động lập lịch trình chi tiết từng ngày dựa trên điểm đến, thời gian, ngân sách và sở thích.',
                            style: TextStyle(
                                fontSize: 13, color: cs.onSurfaceVariant),
                          ),
                          const SizedBox(height: 12),
                          if (state.isGeneratingPlan)
                            const AppLoading(
                              isCompact: true,
                              message: 'Wandy đang lên lịch trình tối ưu...',
                            )
                          else
                            AppButton(
                              text: 'Lập lịch trình bằng AI',
                              variant: AppButtonVariant.ai,
                              onPressed: _handleGenerateAiPlan,
                            ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Itinerary Header
                  Row(
                    children: [
                      const Expanded(
                        child: Text(
                          'Lịch trình chi tiết',
                          style: TextStyle(
                              fontSize: 17, fontWeight: FontWeight.bold),
                        ),
                      ),
                      if (!_isReordering)
                        TextButton.icon(
                          onPressed: () => _showAddItineraryDialog(1),
                          icon: const Icon(Icons.add, size: 18),
                          label: const Text('Thêm hoạt động'),
                        ),
                    ],
                  ),
                  if (!_isReordering &&
                      trip.status != 'CANCELLED' &&
                      trip.itineraries.any((d) => d.items.length >= 2))
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton.icon(
                        key: const Key('trip_itinerary_reorder_toggle'),
                        onPressed: () => _enterReorderMode(trip),
                        style: TextButton.styleFrom(
                          visualDensity: VisualDensity.compact,
                        ),
                        icon: const Icon(Icons.swap_vert, size: 18),
                        label: const Text('Đổi thứ tự'),
                      ),
                    ),
                  if (_isReordering)
                    Container(
                      key: const Key('trip_itinerary_reorder_toolbar'),
                      margin: const EdgeInsets.only(top: 8),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: cs.primaryContainer.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: cs.primary.withValues(alpha: 0.35),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.drag_indicator,
                                size: 18,
                                color: cs.primary,
                              ),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  'Kéo giữ biểu tượng ≡ để đổi thứ tự hoạt động, sau đó nhấn Lưu thứ tự.',
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: cs.onSurface,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 10),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              TextButton(
                                key: const Key('trip_itinerary_reorder_cancel'),
                                onPressed: state.isSavingOrder
                                    ? null
                                    : _cancelReorderMode,
                                child: const Text('Hủy'),
                              ),
                              const SizedBox(width: 8),
                              AppButton(
                                key: const Key('trip_itinerary_reorder_save'),
                                text: 'Lưu thứ tự',
                                icon: Icons.check,
                                isFullWidth: false,
                                isLoading: state.isSavingOrder,
                                onPressed: _saveReorderedItinerary,
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
          if (trip.itineraries.isEmpty)
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                0,
                AppSpacing.md,
                AppSpacing.lg,
              ),
              sliver: SliverToBoxAdapter(
                child: Card(
                  elevation: 0,
                  color: cs.surfaceContainerLow,
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12)),
                  child: const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(
                      child: Text(
                        'Chưa có lịch trình. Hãy nhấn "Thêm hoạt động" để bắt đầu!',
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ),
                ),
              ),
            )
          else if (_isReordering)
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                0,
                AppSpacing.md,
                AppSpacing.xl,
              ),
              sliver: SliverList.builder(
                itemCount: _draftItineraries.length,
                itemBuilder: (context, dayIdx) {
                  return _buildReorderableDaySection(
                    _draftItineraries[dayIdx],
                    cs,
                    isDisabled: state.isSavingOrder,
                  );
                },
              ),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                0,
                AppSpacing.md,
                AppSpacing.xl,
              ),
              sliver: SliverList.builder(
                itemCount: entries.length,
                itemBuilder: (context, index) {
                  final entry = entries[index];
                  switch (entry) {
                    case _DayHeaderEntry(:final day):
                      return _buildDayHeader(day, cs);
                    case _EmptyDayEntry():
                      return _buildEmptyDayCard(cs);
                    case _DayItemEntry(:final item, :final isLastInDay):
                      return _buildLazyItemCard(item, cs, isLastInDay);
                  }
                },
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildInfoColumn(
    String label,
    String value,
    IconData icon,
    ColorScheme cs,
  ) {
    return Column(
      children: [
        Icon(icon, size: 20, color: cs.primary),
        const SizedBox(height: 4),
        Text(
          label,
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
        ),
      ],
    );
  }

  Widget _buildDayHeader(ItineraryModel day, ColorScheme cs) {
    final borderColor = cs.outlineVariant.withValues(alpha: 0.5);
    return Container(
      margin: const EdgeInsets.only(top: 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: cs.surfaceContainerLow,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(14)),
        border: Border(
          top: BorderSide(color: borderColor),
          left: BorderSide(color: borderColor),
          right: BorderSide(color: borderColor),
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: Text(
              day.title != null && day.title!.isNotEmpty
                  ? (day.title!.startsWith('Ngay') ||
                          day.title!.startsWith('Ngày')
                      ? day.title!
                      : 'Ngày ${day.dayNumber}: ${day.title}')
                  : 'Ngày ${day.dayNumber}',
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
            ),
          ),
          TextButton(
            onPressed: () => _showAddItineraryDialog(day.dayNumber),
            style: TextButton.styleFrom(
              visualDensity: VisualDensity.compact,
              padding: EdgeInsets.zero,
            ),
            child: const Text('+ Hoạt động', style: TextStyle(fontSize: 12)),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyDayCard(ColorScheme cs) {
    final borderColor = cs.outlineVariant.withValues(alpha: 0.5);
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(14)),
        border: Border.all(color: borderColor),
      ),
      child: const Text('Chưa có hoạt động nào trong ngày này.'),
    );
  }

  Widget _buildReorderableDaySection(
    ItineraryModel day,
    ColorScheme cs, {
    required bool isDisabled,
  }) {
    final borderColor = cs.outlineVariant.withValues(alpha: 0.5);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          margin: const EdgeInsets.only(top: 4),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: cs.surfaceContainerLow,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(14)),
            border: Border(
              top: BorderSide(color: borderColor),
              left: BorderSide(color: borderColor),
              right: BorderSide(color: borderColor),
            ),
          ),
          child: Text(
            day.title != null && day.title!.isNotEmpty
                ? (day.title!.startsWith('Ngay') ||
                        day.title!.startsWith('Ngày')
                    ? day.title!
                    : 'Ngày ${day.dayNumber}: ${day.title}')
                : 'Ngày ${day.dayNumber}',
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
          ),
        ),
        if (day.items.isEmpty)
          _buildEmptyDayCard(cs)
        else
          Container(
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: cs.surface,
              borderRadius:
                  const BorderRadius.vertical(bottom: Radius.circular(14)),
              border: Border.all(color: borderColor),
            ),
            clipBehavior: Clip.antiAlias,
            child: ReorderableListView.builder(
              key: Key('trip_reorder_list_day_${day.dayNumber}'),
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              buildDefaultDragHandles: false,
              itemCount: day.items.length,
              onReorderItem: (oldIndex, newIndex) {
                if (isDisabled) return;
                _handleDraftDayReorder(day.dayNumber, oldIndex, newIndex);
              },
              itemBuilder: (context, itemIndex) {
                final item = day.items[itemIndex];
                final isLast = itemIndex == day.items.length - 1;
                return Container(
                  key: ValueKey('trip_reorder_tile_${item.id}'),
                  decoration: BoxDecoration(
                    color: cs.surface,
                    border: isLast
                        ? null
                        : Border(bottom: BorderSide(color: borderColor)),
                  ),
                  child: ListTile(
                    leading: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        ReorderableDragStartListener(
                          index: itemIndex,
                          enabled: !isDisabled,
                          child: Container(
                            key: Key('trip_reorder_handle_${item.id}'),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 6,
                              vertical: 8,
                            ),
                            child: Icon(
                              Icons.drag_handle,
                              color: cs.onSurfaceVariant,
                            ),
                          ),
                        ),
                        const SizedBox(width: 4),
                        Container(
                          key: Key('trip_reorder_badge_${item.id}'),
                          width: 30,
                          height: 30,
                          decoration: BoxDecoration(
                            color: cs.primary.withValues(alpha: 0.12),
                            shape: BoxShape.circle,
                          ),
                          child: Center(
                            child: Text(
                              '${item.orderIndex}',
                              style: TextStyle(
                                color: cs.primary,
                                fontWeight: FontWeight.bold,
                                fontSize: 13,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    title: Text(
                      item.activity,
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 14,
                      ),
                    ),
                    subtitle: item.placeId != null
                        ? Padding(
                            padding: const EdgeInsets.only(top: 2),
                            child: Text(
                              item.placeName ?? 'Địa điểm đã lưu',
                              key: Key('trip_reorder_place_${item.placeId}'),
                              style: TextStyle(
                                fontSize: 12,
                                color: cs.primary,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          )
                        : null,
                  ),
                );
              },
            ),
          ),
      ],
    );
  }

  Widget _buildLazyItemCard(
    ItineraryItemModel item,
    ColorScheme cs,
    bool isLastInDay,
  ) {
    final borderColor = cs.outlineVariant.withValues(alpha: 0.5);
    final radius = isLastInDay
        ? const BorderRadius.vertical(bottom: Radius.circular(14))
        : BorderRadius.zero;
    return Container(
      margin: EdgeInsets.only(bottom: isLastInDay ? 12 : 0),
      foregroundDecoration: BoxDecoration(
        borderRadius: radius,
        border: Border(
          left: BorderSide(color: borderColor),
          right: BorderSide(color: borderColor),
          bottom: BorderSide(color: borderColor),
        ),
      ),
      child: Material(
        color: cs.surface,
        borderRadius: radius,
        clipBehavior: Clip.antiAlias,
        child: _buildItineraryItemRow(item, cs),
      ),
    );
  }

  Widget _buildItineraryItemRow(ItineraryItemModel item, ColorScheme cs) {
    final timeRange = formatItineraryTimeRange(item.startTime, item.endTime);
    return ListTile(
      key: Key('trip_itinerary_item_${item.id}'),
      onTap: item.placeId != null
          ? () => context.push('/places/${item.placeId}')
          : null,
      leading: Container(
        width: 36,
        height: 36,
        decoration: BoxDecoration(
          color: cs.primary.withValues(alpha: 0.1),
          shape: BoxShape.circle,
        ),
        child: Center(
          child: Text(
            '${item.orderIndex}',
            style: TextStyle(color: cs.primary, fontWeight: FontWeight.bold),
          ),
        ),
      ),
      title: Text(
        item.activity,
        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14),
      ),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (item.placeId != null)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.place_outlined, size: 13, color: cs.primary),
                  const SizedBox(width: 3),
                  Flexible(
                    child: Text(
                      item.placeName ?? 'Xem chi tiết địa điểm đã lưu',
                      key: Key('trip_item_place_${item.placeId}'),
                      style: TextStyle(
                        fontSize: 12,
                        color: cs.primary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          if (timeRange != null)
            Text(
              'Thời gian: $timeRange',
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
            ),
          Text(
            item.estimatedCost != null
                ? 'Chi phí: ${item.estimatedCost} VND'
                : 'Chi phí: Chưa biết',
            style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
          ),
          if (item.notes != null && item.notes!.isNotEmpty)
            Text(
              'Ghi chú: ${item.notes}',
              style: TextStyle(fontSize: 11, color: cs.outline),
            ),
        ],
      ),
      trailing: IconButton(
        icon: const Icon(Icons.delete_outline, size: 20),
        tooltip: 'Xóa hoạt động',
        onPressed: () async {
          final ok = await ref
              .read(tripDetailProvider.notifier)
              .deleteItineraryItem(widget.tripId, item.id);
          if (!ok && mounted) {
            final err = ref.read(tripDetailProvider).errorMessage ??
                'Không thể xóa hoạt động khỏi lịch trình';
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                key: const Key('trip_itinerary_error_snackbar'),
                content: Text(err),
              ),
            );
          }
        },
      ),
    );
  }
}

class _AddItinerarySheet extends StatefulWidget {
  final int defaultDay;
  final Future<void> Function(AddItineraryItemRequest request) onSubmit;

  const _AddItinerarySheet({
    required this.defaultDay,
    required this.onSubmit,
  });

  @override
  State<_AddItinerarySheet> createState() => _AddItinerarySheetState();
}

class _AddItinerarySheetState extends State<_AddItinerarySheet> {
  final _activityController = TextEditingController();
  final _timeController = TextEditingController();
  final _costController = TextEditingController();
  final _notesController = TextEditingController();
  late int _selectedDay;
  String? _dialogError;

  @override
  void initState() {
    super.initState();
    _selectedDay = widget.defaultDay;
  }

  @override
  void dispose() {
    _activityController.dispose();
    _timeController.dispose();
    _costController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        right: 20,
        top: 20,
        bottom: MediaQuery.of(context).viewInsets.bottom + 20,
      ),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Thêm hoạt động vào lịch trình',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                const Text('Ngày thứ: '),
                const SizedBox(width: 8),
                DropdownButton<int>(
                  value: _selectedDay,
                  items: List.generate(
                    14,
                    (i) => DropdownMenuItem(
                      value: i + 1,
                      child: Text('Ngày ${i + 1}'),
                    ),
                  ),
                  onChanged: (val) {
                    if (val != null) setState(() => _selectedDay = val);
                  },
                ),
              ],
            ),
            const SizedBox(height: 10),
            AppTextField(
              key: const Key('trip_add_item_activity_input'),
              controller: _activityController,
              labelText: 'Hoạt động / Địa điểm *',
              hintText: 'VD: Tham quan Hồ Gươm',
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: AppTextField(
                    key: const Key('trip_add_item_time_input'),
                    controller: _timeController,
                    labelText: 'Thời gian',
                    hintText: '09:00',
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: AppTextField(
                    key: const Key('trip_add_item_cost_input'),
                    controller: _costController,
                    keyboardType: TextInputType.number,
                    labelText: 'Chi phí (VND)',
                    hintText: '100000',
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            AppTextField(
              key: const Key('trip_add_item_notes_input'),
              controller: _notesController,
              labelText: 'Ghi chú',
              hintText: 'Lưu ý, địa chỉ...',
            ),
            if (_dialogError != null) ...[
              const SizedBox(height: 10),
              Text(
                _dialogError!,
                key: const Key('trip_add_item_dialog_error'),
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
            const SizedBox(height: 20),
            AppButton(
              key: const Key('trip_add_item_submit_button'),
              text: 'Thêm vào lịch trình',
              onPressed: () async {
                final activity = _activityController.text.trim();
                if (activity.isEmpty) {
                  setState(() => _dialogError = 'Vui lòng nhập tên hoạt động');
                  return;
                }

                final rawCost = _costController.text.trim();
                int? cost;
                if (rawCost.isNotEmpty) {
                  cost = int.tryParse(rawCost);
                  if (cost == null || cost < 0) {
                    setState(
                      () => _dialogError = 'Chi phí phải là số nguyên không âm',
                    );
                    return;
                  }
                }

                final req = AddItineraryItemRequest(
                  dayNumber: _selectedDay,
                  activity: activity,
                  startTime: _timeController.text.trim(),
                  estimatedCost: cost,
                  notes: _notesController.text.trim(),
                );
                Navigator.pop(context);
                await widget.onSubmit(req);
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _AiPlanPromptDialog extends StatefulWidget {
  const _AiPlanPromptDialog();

  @override
  State<_AiPlanPromptDialog> createState() => _AiPlanPromptDialogState();
}

class _AiPlanPromptDialogState extends State<_AiPlanPromptDialog> {
  final TextEditingController _noteController = TextEditingController();

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Lập lịch trình bằng AI'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Wandy sẽ sử dụng thông tin chuyến đi (điểm đến, ngày, ngân sách, sở thích) để lên lịch trình tối ưu nhất.',
            ),
            const SizedBox(height: 12),
            AppTextField(
              key: const Key('trip_ai_plan_prompt_input'),
              controller: _noteController,
              labelText: 'Yêu cầu thêm (tùy chọn)',
              hintText: 'VD: Ưu tiên quán ăn ngon, chụp ảnh...',
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          key: const Key('trip_ai_plan_cancel_button'),
          onPressed: () => Navigator.pop(context),
          child: const Text('Hủy'),
        ),
        AppButton(
          key: const Key('trip_ai_plan_confirm_button'),
          text: 'Bắt đầu lập',
          variant: AppButtonVariant.ai,
          isFullWidth: false,
          onPressed: () => Navigator.pop(context, _noteController.text.trim()),
        ),
      ],
    );
  }
}
