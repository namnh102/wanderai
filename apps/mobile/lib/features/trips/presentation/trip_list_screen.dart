import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../data/trip_models.dart';
import '../providers/trip_provider.dart';

class TripListScreen extends ConsumerWidget {
  const TripListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(tripListProvider);
    final cs = Theme.of(context).colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Chuyến đi của tôi',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.add_circle_outline),
            tooltip: 'Tạo chuyến đi mới',
            onPressed: () => context.push('/trips/create'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(tripListProvider.notifier).loadTrips(),
        child: _buildContent(context, ref, state, cs),
      ),
    );
  }

  Widget _buildContent(
    BuildContext context,
    WidgetRef ref,
    TripListState state,
    ColorScheme cs,
  ) {
    if (state.isLoading && state.trips.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (state.errorMessage != null && state.trips.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.error_outline, size: 48, color: cs.error),
              const SizedBox(height: 16),
              Text(
                state.errorMessage!,
                textAlign: TextAlign.center,
                style: TextStyle(color: cs.onSurface),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () =>
                    ref.read(tripListProvider.notifier).loadTrips(),
                child: const Text('Thử lại'),
              ),
            ],
          ),
        ),
      );
    }

    if (state.isEmpty) {
      return Center(
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: cs.primary.withValues(alpha: 0.12),
                  shape: BoxShape.circle,
                ),
                child:
                    Icon(Icons.luggage_outlined, size: 40, color: cs.primary),
              ),
              const SizedBox(height: 20),
              const Text(
                'Chưa có chuyến đi nào',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                'Hãy bắt đầu lên kế hoạch cho chuyến du lịch tiếp theo của bạn ngay bây giờ!',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 14, color: cs.onSurfaceVariant),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: () => context.push('/trips/create'),
                icon: const Icon(Icons.add),
                label: const Text('Tạo chuyến đi mới'),
              ),
            ],
          ),
        ),
      );
    }

    return ListView.builder(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      itemCount: state.trips.length,
      itemBuilder: (context, index) {
        final trip = state.trips[index];
        return _buildTripCard(context, ref, trip, cs);
      },
    );
  }

  Widget _buildTripCard(
    BuildContext context,
    WidgetRef ref,
    TripModel trip,
    ColorScheme cs,
  ) {
    return Card(
      key: Key('trip_card_${trip.id}'),
      margin: const EdgeInsets.only(bottom: 14),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: cs.outlineVariant.withValues(alpha: 0.6)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () => context.push('/trips/${trip.id}'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      trip.title,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  _buildStatusChip(trip.status, cs),
                ],
              ),
              if (trip.destinationName != null) ...[
                const SizedBox(height: 6),
                Row(
                  children: [
                    Icon(Icons.location_on_outlined,
                        size: 16, color: cs.primary),
                    const SizedBox(width: 4),
                    Text(
                      trip.destinationName!,
                      style: TextStyle(
                        fontSize: 13,
                        color: cs.primary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 10),
              Row(
                children: [
                  if (trip.startDate != null) ...[
                    Icon(Icons.calendar_today_outlined,
                        size: 14, color: cs.onSurfaceVariant),
                    const SizedBox(width: 4),
                    Text(
                      _formatDateRange(trip.startDate, trip.endDate),
                      style: TextStyle(
                        fontSize: 12,
                        color: cs.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(width: 14),
                  ],
                  if (trip.totalBudget != null) ...[
                    Icon(Icons.payments_outlined,
                        size: 14, color: cs.onSurfaceVariant),
                    const SizedBox(width: 4),
                    Text(
                      '${_formatCurrency(trip.totalBudget!)} ${trip.currency}',
                      style: TextStyle(
                        fontSize: 12,
                        color: cs.onSurfaceVariant,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatusChip(String status, ColorScheme cs) {
    Color bg;
    Color fg;
    String label;

    switch (status) {
      case 'PLANNED':
        bg = cs.primaryContainer;
        fg = cs.onPrimaryContainer;
        label = 'Đã lên lịch';
        break;
      case 'ONGOING':
        bg = Colors.amber.shade100;
        fg = Colors.amber.shade900;
        label = 'Đang đi';
        break;
      case 'COMPLETED':
        bg = Colors.green.shade100;
        fg = Colors.green.shade900;
        label = 'Hoàn thành';
        break;
      default:
        bg = cs.surfaceContainerHigh;
        fg = cs.onSurfaceVariant;
        label = 'Bản nháp';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        label,
        style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: fg),
      ),
    );
  }

  String _formatDateRange(DateTime? start, DateTime? end) {
    if (start == null) return '';
    final sStr = '${start.day}/${start.month}/${start.year}';
    if (end == null) return sStr;
    final eStr = '${end.day}/${end.month}/${end.year}';
    return '$sStr - $eStr';
  }

  String _formatCurrency(int amount) {
    return amount.toString().replaceAllMapped(
          RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
          (Match m) => '${m[1]}.',
        );
  }
}
