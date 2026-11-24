import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/widgets/app_empty_state.dart';
import '../../../core/widgets/app_error_state.dart';
import '../../../core/widgets/app_loading.dart';
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
      return const AppLoading(message: 'Đang tải danh sách chuyến đi...');
    }

    if (state.errorMessage != null && state.trips.isEmpty) {
      return AppErrorState(
        title: state.isOfflineError
            ? 'Không có kết nối mạng'
            : 'Không thể tải dữ liệu',
        message: state.errorMessage!,
        onRetry: () => ref.read(tripListProvider.notifier).loadTrips(),
      );
    }

    if (state.isEmpty) {
      return LayoutBuilder(
        builder: (context, constraints) => SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: constraints.maxHeight),
            child: AppEmptyState(
              icon: Icons.luggage_outlined,
              title: 'Chưa có chuyến đi nào',
              description:
                  'Hãy bắt đầu lên kế hoạch cho chuyến du lịch tiếp theo của bạn ngay bây giờ!',
              actionLabel: 'Tạo chuyến đi mới',
              onAction: () => context.push('/trips/create'),
            ),
          ),
        ),
      );
    }

    return ListView.builder(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: state.trips.length,
      itemBuilder: (context, index) {
        final trip = state.trips[index];
        return _buildTripCard(context, trip, cs);
      },
    );
  }

  Widget _buildTripCard(
    BuildContext context,
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
        bg = AppColors.warningContainer;
        fg = AppColors.warning;
        label = 'Đang đi';
        break;
      case 'COMPLETED':
        bg = AppColors.successContainer;
        fg = AppColors.success;
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
