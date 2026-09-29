import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/network/api_client.dart';
import 'package:google_fonts/google_fonts.dart';

// Provider lấy danh sách trips từ API
final tripsProvider = FutureProvider<List<dynamic>>((ref) async {
  try {
    final response = await apiClient.get('/trips');
    final data = response.data;
    if (data['success'] == true) {
      return List<dynamic>.from(data['data'] ?? []);
    }
    return [];
  } catch (_) {
    return [];
  }
});

class TripScreen extends ConsumerWidget {
  const TripScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tripsAsync = ref.watch(tripsProvider);

    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        backgroundColor: AppTheme.surface,
        elevation: 0,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Chuyen di cua toi',
                style: GoogleFonts.plusJakartaSans(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: AppTheme.onSurface)),
            Text('Quan ly hanh trinh du lich',
                style: GoogleFonts.plusJakartaSans(
                    fontSize: 13, color: AppTheme.onSurfaceVariant)),
          ],
        ),
        actions: [
          IconButton(
            icon: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.primary,
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.add, color: Colors.white, size: 20),
            ),
            onPressed: () => _showCreateTripDialog(context, ref),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: tripsAsync.when(
        loading: () => const Center(
          child: CircularProgressIndicator(color: AppTheme.primary),
        ),
        error: (_, __) => _buildEmptyState(context, ref),
        data: (trips) => trips.isEmpty
            ? _buildEmptyState(context, ref)
            : _buildTripList(context, ref, trips),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context, WidgetRef ref) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 100,
            height: 100,
            decoration: BoxDecoration(
              color: AppTheme.primaryFixed,
              borderRadius: BorderRadius.circular(28),
            ),
            child: const Icon(Icons.luggage_outlined,
                size: 52, color: AppTheme.primary),
          ),
          const SizedBox(height: 20),
          Text('Chua co chuyen di nao',
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: AppTheme.onSurface)),
          const SizedBox(height: 8),
          Text('Bat dau ke hoach hanh trinh tuyet voi cua ban!',
              textAlign: TextAlign.center,
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 14, color: AppTheme.onSurfaceVariant)),
          const SizedBox(height: 28),
          ElevatedButton.icon(
            onPressed: () => _showCreateTripDialog(context, ref),
            icon: const Icon(Icons.add),
            label: const Text('Tao chuyen di moi'),
          ),
        ],
      ),
    );
  }

  Widget _buildTripList(
      BuildContext context, WidgetRef ref, List<dynamic> trips) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: trips.length,
      itemBuilder: (context, index) {
        final trip = trips[index] as Map<String, dynamic>;
        return _TripCard(trip: trip, ref: ref);
      },
    );
  }

  void _showCreateTripDialog(BuildContext context, WidgetRef ref) {
    final titleCtrl = TextEditingController();
    final startCtrl = TextEditingController();
    final endCtrl = TextEditingController();
    final budgetCtrl = TextEditingController();

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(ctx).viewInsets.bottom + 16,
          top: 16,
          left: 20,
          right: 20,
        ),
        decoration: const BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppTheme.outline.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text('Tao chuyen di moi',
                style: GoogleFonts.plusJakartaSans(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: AppTheme.onSurface)),
            const SizedBox(height: 20),
            TextField(
              controller: titleCtrl,
              decoration: const InputDecoration(
                labelText: 'Ten chuyen di',
                prefixIcon: Icon(Icons.drive_file_rename_outline),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: startCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Ngay di (YYYY-MM-DD)',
                      prefixIcon: Icon(Icons.calendar_today, size: 18),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: endCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Ngay ve',
                      prefixIcon: Icon(Icons.event, size: 18),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: budgetCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Ngan sach (VND)',
                prefixIcon: Icon(Icons.payments_outlined),
              ),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: () async {
                if (titleCtrl.text.isEmpty) return;
                try {
                  await apiClient.post('/trips', data: {
                    'title': titleCtrl.text.trim(),
                    if (startCtrl.text.isNotEmpty)
                      'startDate': startCtrl.text.trim(),
                    if (endCtrl.text.isNotEmpty)
                      'endDate': endCtrl.text.trim(),
                    if (budgetCtrl.text.isNotEmpty)
                      'totalBudget': int.tryParse(budgetCtrl.text) ?? 0,
                  });
                  ref.invalidate(tripsProvider);
                  if (!ctx.mounted) return;
                  Navigator.pop(ctx);
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: const Text('Tao chuyen di thanh cong!'),
                      backgroundColor: AppTheme.primary,
                      behavior: SnackBarBehavior.floating,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10)),
                    ),
                  );
                } catch (_) {
                  if (!ctx.mounted) return;
                  Navigator.pop(ctx);
                }
              },
              child: const Text('Tao ngay'),
            ),
          ],
        ),
      ),
    );
  }
}

class _TripCard extends StatelessWidget {
  final Map<String, dynamic> trip;
  final WidgetRef ref;
  const _TripCard({required this.trip, required this.ref});

  Color _statusColor(String? status) {
    switch (status) {
      case 'PLANNED':
        return AppTheme.primary;
      case 'ONGOING':
        return Colors.orange;
      case 'COMPLETED':
        return Colors.green;
      case 'CANCELLED':
        return AppTheme.error;
      default:
        return AppTheme.outline;
    }
  }

  String _statusLabel(String? status) {
    switch (status) {
      case 'PLANNED':
        return 'Da ke hoach';
      case 'ONGOING':
        return 'Dang di';
      case 'COMPLETED':
        return 'Hoan thanh';
      case 'CANCELLED':
        return 'Da huy';
      default:
        return 'Nhap';
    }
  }

  @override
  Widget build(BuildContext context) {
    final startDate = trip['startDate'] != null
        ? trip['startDate'].toString().substring(0, 10)
        : '--';
    final endDate = trip['endDate'] != null
        ? trip['endDate'].toString().substring(0, 10)
        : '--';
    final budget = trip['totalBudget'];
    final status = trip['status'] as String?;

    return GestureDetector(
      onTap: () => context.go('/trips/${trip['id']}'),
      child: Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: AppTheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: AppTheme.onSurface.withValues(alpha: 0.06),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(trip['title'] ?? 'Chuyen di',
                      style: GoogleFonts.plusJakartaSans(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: AppTheme.onSurface)),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _statusColor(status).withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(_statusLabel(status),
                      style: GoogleFonts.plusJakartaSans(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          color: _statusColor(status))),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                _InfoChip(
                    icon: Icons.calendar_today, label: '$startDate - $endDate'),
                const SizedBox(width: 8),
                if (budget != null)
                  _InfoChip(
                      icon: Icons.payments_outlined,
                      label:
                          '${(budget / 1000000).toStringAsFixed(1)}tr VND'),
              ],
            ),
          ],
        ),
      ),
    ), // GestureDetector child end
    );  // GestureDetector end
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  const _InfoChip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppTheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: AppTheme.primary),
          const SizedBox(width: 4),
          Text(label,
              style: GoogleFonts.plusJakartaSans(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.onSurfaceVariant)),
        ],
      ),
    );
  }
}
