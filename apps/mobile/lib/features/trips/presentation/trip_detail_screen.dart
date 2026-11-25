import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../data/trip_models.dart';
import '../providers/trip_provider.dart';
import 'trip_form_screen.dart';

class TripDetailScreen extends ConsumerStatefulWidget {
  final String tripId;

  const TripDetailScreen({super.key, required this.tripId});

  @override
  ConsumerState<TripDetailScreen> createState() => _TripDetailScreenState();
}

class _TripDetailScreenState extends ConsumerState<TripDetailScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() async {
      await ref.read(tripDetailProvider.notifier).loadTrip(widget.tripId);
      if (!mounted) return;
      final loaded = ref.read(tripDetailProvider).trip;
      if (kDebugMode && loaded != null) {
        final placeIds = loaded.itineraries
            .expand((d) => d.items)
            .map((i) => i.placeId)
            .whereType<String>()
            .toList();
        debugPrint(
          '[GoMate][TripDetail] opened trip_id=${loaded.id} '
          'title="${loaded.title}" place_ids=$placeIds',
        );
      }
    });
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
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            child: const Text('Xóa'),
          ),
        ],
      ),
    );

    if (confirm == true && mounted) {
      final success =
          await ref.read(tripListProvider.notifier).deleteTrip(widget.tripId);
      if (mounted) {
        if (success) {
          context.pop();
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
    final noteController = TextEditingController();
    final shouldProceed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Lập lịch trình bằng AI'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Wandy sẽ sử dụng thông tin chuyến đi (điểm đến, ngày, ngân sách, sở thích) để lên lịch trình tối ưu nhất.',
            ),
            const SizedBox(height: 12),
            TextField(
              controller: noteController,
              decoration: const InputDecoration(
                labelText: 'Yêu cầu thêm (tùy chọn)',
                hintText: 'VD: Ưu tiên quán ăn ngon, chụp ảnh...',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Hủy'),
          ),
          FilledButton.icon(
            onPressed: () => Navigator.pop(ctx, true),
            icon: const Icon(Icons.auto_awesome, size: 16),
            label: const Text('Bắt đầu lập'),
          ),
        ],
      ),
    );

    if (shouldProceed != true || !mounted) return;

    final prompt = noteController.text.trim();
    final plan = await ref.read(tripDetailProvider.notifier).generateAiPlan(
        widget.tripId,
        prompt: prompt.isNotEmpty ? prompt : null);

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
                child: ListView(
                  controller: scrollCtrl,
                  children: [
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
                      padding: const EdgeInsets.all(12),
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: plan.budgetAnalysis.isOverBudget
                            ? cs.errorContainer.withValues(alpha: 0.3)
                            : cs.primaryContainer.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: plan.budgetAnalysis.isOverBudget
                              ? cs.error
                              : cs.primary,
                        ),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Chi phí ước tính:',
                                  style: TextStyle(
                                      fontSize: 12, color: cs.onSurfaceVariant),
                                ),
                                Text(
                                  '${plan.budgetAnalysis.estimatedCost} ${plan.budgetAnalysis.currency}',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 16,
                                    color: plan.budgetAnalysis.isOverBudget
                                        ? cs.error
                                        : cs.primary,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          if (plan.budgetAnalysis.totalBudget != null) ...[
                            const SizedBox(width: 8),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(
                                  'Ngân sách: ${plan.budgetAnalysis.totalBudget} ${plan.budgetAnalysis.currency}',
                                  style: TextStyle(
                                      fontSize: 12, color: cs.onSurfaceVariant),
                                ),
                                Text(
                                  plan.budgetAnalysis.isOverBudget
                                      ? 'Vượt ${-plan.budgetAnalysis.variance} VND'
                                      : 'Còn dư ${plan.budgetAnalysis.variance} VND',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.bold,
                                    color: plan.budgetAnalysis.isOverBudget
                                        ? cs.error
                                        : cs.primary,
                                  ),
                                ),
                              ],
                            ),
                          ],
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
                                style: TextStyle(
                                    fontSize: 12, color: Colors.amber.shade900),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ...plan.days.map((day) => Container(
                          margin: const EdgeInsets.only(bottom: 12),
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: cs.surface,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                                color:
                                    cs.outlineVariant.withValues(alpha: 0.5)),
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
                                          fontWeight: FontWeight.bold,
                                          fontSize: 14),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    '${day.dayCost} VND',
                                    style: TextStyle(
                                        fontSize: 12,
                                        color: cs.primary,
                                        fontWeight: FontWeight.bold),
                                  ),
                                ],
                              ),
                              const Divider(height: 16),
                              ...day.items.map((item) => Padding(
                                    padding:
                                        const EdgeInsets.symmetric(vertical: 4),
                                    child: Row(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          '${item.orderIndex}. ',
                                          style: TextStyle(
                                              fontWeight: FontWeight.bold,
                                              color: cs.primary),
                                        ),
                                        Expanded(
                                          child: Column(
                                            crossAxisAlignment:
                                                CrossAxisAlignment.start,
                                            children: [
                                              Text(
                                                item.activity,
                                                style: const TextStyle(
                                                    fontWeight: FontWeight.w600,
                                                    fontSize: 13),
                                              ),
                                              if (item.startTime != null)
                                                Text(
                                                  '${item.startTime} - ${item.estimatedCost} VND',
                                                  style: TextStyle(
                                                      fontSize: 11,
                                                      color:
                                                          cs.onSurfaceVariant),
                                                ),
                                            ],
                                          ),
                                        ),
                                      ],
                                    ),
                                  )),
                            ],
                          ),
                        )),
                    const SizedBox(height: 20),
                  ],
                ),
              ),
              SafeArea(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: () => Navigator.pop(ctx),
                          child: const Text('Hủy'),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        flex: 2,
                        child: FilledButton.icon(
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
                                  SnackBar(content: Text(err)),
                                );
                              }
                            }
                          },
                          icon: const Icon(Icons.check, size: 18),
                          label: const Text('Áp dụng vào chuyến đi'),
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

  void _showAddItineraryDialog(int defaultDay) {
    final activityController = TextEditingController();
    final timeController = TextEditingController();
    final costController = TextEditingController();
    final notesController = TextEditingController();
    int selectedDay = defaultDay;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => Padding(
          padding: EdgeInsets.only(
            left: 20,
            right: 20,
            top: 20,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
          ),
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
                    value: selectedDay,
                    items: List.generate(
                      14,
                      (i) => DropdownMenuItem(
                        value: i + 1,
                        child: Text('Ngày ${i + 1}'),
                      ),
                    ),
                    onChanged: (val) {
                      if (val != null) setModalState(() => selectedDay = val);
                    },
                  ),
                ],
              ),
              const SizedBox(height: 10),
              TextField(
                controller: activityController,
                decoration: const InputDecoration(
                  labelText: 'Hoạt động / Địa điểm *',
                  hintText: 'VD: Tham quan Hồ Gươm',
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: timeController,
                      decoration: const InputDecoration(
                        labelText: 'Thời gian',
                        hintText: '09:00',
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: TextField(
                      controller: costController,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Chi phí (VND)',
                        hintText: '100000',
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              TextField(
                controller: notesController,
                decoration: const InputDecoration(
                  labelText: 'Ghi chú',
                  hintText: 'Lưu ý, địa chỉ...',
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () async {
                    final activity = activityController.text.trim();
                    if (activity.isEmpty) return;

                    final cost = int.tryParse(costController.text.trim());
                    Navigator.pop(ctx);

                    await ref
                        .read(tripDetailProvider.notifier)
                        .addItineraryItem(
                          widget.tripId,
                          AddItineraryItemRequest(
                            dayNumber: selectedDay,
                            activity: activity,
                            startTime: timeController.text.trim(),
                            estimatedCost: cost,
                            notes: notesController.text.trim(),
                          ),
                        );
                  },
                  child: const Text('Thêm vào lịch trình'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(tripDetailProvider);
    final cs = Theme.of(context).colorScheme;

    if (state.trip == null) {
      if (state.errorMessage != null) {
        return Scaffold(
          appBar: AppBar(),
          body: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.error_outline, size: 48, color: cs.error),
                const SizedBox(height: 12),
                Text(state.errorMessage!),
                const SizedBox(height: 12),
                ElevatedButton(
                  onPressed: () => ref
                      .read(tripDetailProvider.notifier)
                      .loadTrip(widget.tripId),
                  child: const Text('Thử lại'),
                ),
              ],
            ),
          ),
        );
      }
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    final trip = state.trip!;

    return Scaffold(
      appBar: AppBar(
        title: Text(
          trip.title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        actions: [
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
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Overview Card
          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16),
              side: BorderSide(color: cs.outlineVariant.withValues(alpha: 0.6)),
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
                      style:
                          TextStyle(fontSize: 14, color: cs.onSurfaceVariant),
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
                                    style: const TextStyle(fontSize: 11)),
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
              side: BorderSide(color: cs.primary.withValues(alpha: 0.3)),
            ),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.auto_awesome, color: cs.primary, size: 20),
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
                    style: TextStyle(fontSize: 13, color: cs.onSurfaceVariant),
                  ),
                  const SizedBox(height: 12),
                  if (state.isGeneratingPlan)
                    Row(
                      children: [
                        const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            'Wandy đang lên lịch trình tối ưu...',
                            style: TextStyle(fontSize: 13, color: cs.primary),
                          ),
                        ),
                      ],
                    )
                  else
                    SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: _handleGenerateAiPlan,
                        icon: const Icon(Icons.auto_awesome, size: 18),
                        label: const Text('Lập lịch trình bằng AI'),
                      ),
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
                  style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
                ),
              ),
              TextButton.icon(
                onPressed: () => _showAddItineraryDialog(1),
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Thêm hoạt động'),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Itinerary list
          if (trip.itineraries.isEmpty)
            Card(
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
            )
          else
            ...trip.itineraries.map((day) => _buildDaySection(day, cs)),
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

  Widget _buildDaySection(ItineraryModel day, ColorScheme cs) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Material(
        color: cs.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: cs.outlineVariant.withValues(alpha: 0.5)),
        ),
        clipBehavior: Clip.antiAlias,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: cs.surfaceContainerLow,
                borderRadius:
                    const BorderRadius.vertical(top: Radius.circular(14)),
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
                      style: const TextStyle(
                          fontWeight: FontWeight.bold, fontSize: 15),
                    ),
                  ),
                  TextButton(
                    onPressed: () => _showAddItineraryDialog(day.dayNumber),
                    style: TextButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                      padding: EdgeInsets.zero,
                    ),
                    child: const Text('+ Hoạt động',
                        style: TextStyle(fontSize: 12)),
                  ),
                ],
              ),
            ),
            if (day.items.isEmpty)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Text('Chưa có hoạt động nào trong ngày này.'),
              )
            else
              ...day.items.map((item) => _buildItineraryItemRow(item, cs)),
          ],
        ),
      ),
    );
  }

  Widget _buildItineraryItemRow(ItineraryItemModel item, ColorScheme cs) {
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
          if (item.startTime != null && item.startTime!.isNotEmpty)
            Text(
              'Thời gian: ${item.startTime}',
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
            ),
          if (item.estimatedCost != null)
            Text(
              'Chi phí: ${item.estimatedCost} VND',
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
        onPressed: () {
          ref
              .read(tripDetailProvider.notifier)
              .deleteItineraryItem(widget.tripId, item.id);
        },
      ),
    );
  }
}
