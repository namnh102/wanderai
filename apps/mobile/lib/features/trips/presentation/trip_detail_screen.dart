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
    Future.microtask(
      () => ref.read(tripDetailProvider.notifier).loadTrip(widget.tripId),
    );
  }

  Future<void> _handleDelete() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Xac nhan xoa'),
        content: const Text('Ban co chac chan muon xoa chuyen di nay khong?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Huy'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(ctx).colorScheme.error,
            ),
            child: const Text('Xoa'),
          ),
        ],
      ),
    );

    if (confirm == true && mounted) {
      final success = await ref
          .read(tripListProvider.notifier)
          .deleteTrip(widget.tripId);
      if (mounted) {
        if (success) {
          context.pop();
        } else {
          final err = ref.read(tripListProvider).errorMessage ?? 'Loi xoa chuyen di';
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(err)));
        }
      }
    }
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
                'Them hoat dong vao lich trinh',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  const Text('Ngay thu: '),
                  const SizedBox(width: 8),
                  DropdownButton<int>(
                    value: selectedDay,
                    items: List.generate(
                      14,
                      (i) => DropdownMenuItem(
                        value: i + 1,
                        child: Text('Ngay ${i + 1}'),
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
                  labelText: 'Hoat dong / Dia diem *',
                  hintText: 'VD: Tham quan Ho Guom',
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: timeController,
                      decoration: const InputDecoration(
                        labelText: 'Thoi gian',
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
                        labelText: 'Chi phi (VND)',
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
                  labelText: 'Ghi chu',
                  hintText: 'Luu y, dia chi...',
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
                  child: const Text('Them vao lich trinh'),
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
                  onPressed: () =>
                      ref.read(tripDetailProvider.notifier).loadTrip(widget.tripId),
                  child: const Text('Thu lai'),
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
            tooltip: 'Chinh sua',
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
            tooltip: 'Xoa chuyen di',
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
                  if (trip.description != null && trip.description!.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(
                      trip.description!,
                      style: TextStyle(fontSize: 14, color: cs.onSurfaceVariant),
                    ),
                  ],
                  const Divider(height: 24),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      _buildInfoColumn(
                        'Ngan sach',
                        trip.totalBudget != null
                            ? '${trip.totalBudget} ${trip.currency}'
                            : 'Chua dat',
                        Icons.payments_outlined,
                        cs,
                      ),
                      _buildInfoColumn(
                        'Thoi gian',
                        trip.startDate != null
                            ? '${trip.startDate!.day}/${trip.startDate!.month}'
                            : 'Chua chon',
                        Icons.calendar_today_outlined,
                        cs,
                      ),
                      _buildInfoColumn(
                        'Phong cach',
                        trip.travelStyle ?? 'Tu do',
                        Icons.explore_outlined,
                        cs,
                      ),
                    ],
                  ),
                  if (trip.interests.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 6,
                      children: trip.interests
                          .map((tag) => Chip(
                                label: Text(tag, style: const TextStyle(fontSize: 11)),
                                visualDensity: VisualDensity.compact,
                              ))
                          .toList(),
                    ),
                  ],
                ],
              ),
            ),
          ),
          const SizedBox(height: 20),

          // Itinerary Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Lich trinh chi tiet',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
              ),
              TextButton.icon(
                onPressed: () => _showAddItineraryDialog(1),
                icon: const Icon(Icons.add, size: 18),
                label: const Text('Them hoat dong'),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Itinerary list
          if (trip.itineraries.isEmpty)
            Card(
              elevation: 0,
              color: cs.surfaceContainerLow,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              child: const Padding(
                padding: EdgeInsets.all(24),
                child: Center(
                  child: Text(
                    'Chua co lich trinh. Hay nhan "Them hoat dong" de bat dau!',
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
          style: TextStyle(fontSize: 11, color: cs.onSurfaceVariant),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold),
        ),
      ],
    );
  }

  Widget _buildDaySection(ItineraryModel day, ColorScheme cs) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: cs.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: cs.outlineVariant.withValues(alpha: 0.5)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: cs.surfaceContainerLow,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(14)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Ngay ${day.dayNumber}',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
                TextButton(
                  onPressed: () => _showAddItineraryDialog(day.dayNumber),
                  style: TextButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    padding: EdgeInsets.zero,
                  ),
                  child: const Text('+ Hoat dong', style: TextStyle(fontSize: 12)),
                ),
              ],
            ),
          ),
          if (day.items.isEmpty)
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('Chua co hoat dong nao trong ngay nay.'),
            )
          else
            ...day.items.map((item) => _buildItineraryItemRow(item, cs)),
        ],
      ),
    );
  }

  Widget _buildItineraryItemRow(ItineraryItemModel item, ColorScheme cs) {
    return ListTile(
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
          if (item.startTime != null && item.startTime!.isNotEmpty)
            Text(
              'Thoi gian: ${item.startTime}',
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
            ),
          if (item.estimatedCost != null)
            Text(
              'Chi phi: ${item.estimatedCost} VND',
              style: TextStyle(fontSize: 12, color: cs.onSurfaceVariant),
            ),
          if (item.notes != null && item.notes!.isNotEmpty)
            Text(
              'Ghi chu: ${item.notes}',
              style: TextStyle(fontSize: 11, color: cs.outline),
            ),
        ],
      ),
      trailing: IconButton(
        icon: const Icon(Icons.delete_outline, size: 20),
        tooltip: 'Xoa hoat dong',
        onPressed: () {
          ref
              .read(tripDetailProvider.notifier)
              .deleteItineraryItem(widget.tripId, item.id);
        },
      ),
    );
  }
}
