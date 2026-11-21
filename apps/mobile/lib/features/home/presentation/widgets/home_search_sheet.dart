import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_button.dart';
import '../../../../core/widgets/app_empty_state.dart';
import '../../../../core/widgets/app_error_state.dart';
import '../../../../core/widgets/app_loading.dart';
import '../../../../core/widgets/app_search_bar.dart';
import '../../../../core/widgets/responsive_wrapper.dart';
import '../../../location/providers/user_location_provider.dart';
import '../../../map/data/place_model.dart';
import '../../../map/providers/map_provider.dart';
import 'home_verified_place_tile.dart';

/// Opens a live Home search sheet backed by `GET /places?search=...&verifiedOnly=true`.
Future<void> showHomeSearchSheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    builder: (ctx) => const _HomeSearchSheet(),
  );
}

class _HomeSearchSheet extends ConsumerStatefulWidget {
  const _HomeSearchSheet();

  @override
  ConsumerState<_HomeSearchSheet> createState() => _HomeSearchSheetState();
}

class _HomeSearchSheetState extends ConsumerState<_HomeSearchSheet> {
  final TextEditingController _controller = TextEditingController();
  Timer? _debounce;
  bool _loading = false;
  String? _error;
  String _submittedQuery = '';
  List<PlaceModel> _results = const [];

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    setState(() {});
    _debounce?.cancel();
    final q = value.trim();
    if (q.isEmpty) {
      setState(() {
        _submittedQuery = '';
        _results = const [];
        _error = null;
        _loading = false;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 350), () => _search(q));
  }

  Future<void> _search(String query) async {
    final q = query.trim();
    if (q.isEmpty || !mounted) return;
    setState(() {
      _loading = true;
      _error = null;
      _submittedQuery = q;
    });
    try {
      final repo = ref.read(placeRepositoryProvider);
      final items = await repo.getPlaces(
        search: q,
        verifiedOnly: true,
        limit: 20,
      );
      if (!mounted || _submittedQuery != q) return;
      setState(() {
        _results = items;
        _loading = false;
      });
    } catch (_) {
      if (!mounted || _submittedQuery != q) return;
      setState(() {
        _error = 'Không thể tìm kiếm địa điểm lúc này. Vui lòng thử lại.';
        _loading = false;
      });
    }
  }

  void _handoffToMap(String query) {
    final q = query.trim();
    Navigator.of(context).pop();
    if (q.isNotEmpty) {
      ref.read(mapProvider.notifier).searchPlaces(q);
    }
    context.go('/map');
  }

  @override
  Widget build(BuildContext context) {
    final userPos = ref.watch(userLocationProvider).position;
    final sheetHeight = MediaQuery.of(context).size.height * 0.85;

    return ResponsiveWrapper(
      maxWidth: 680.0,
      fillHeight: false,
      child: Container(
        height: sheetHeight,
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: AppRadius.sheetRadius,
        ),
        child: Column(
          children: [
            const SizedBox(height: AppSpacing.sm),
            Container(
              width: 40,
              height: 4,
              decoration: const BoxDecoration(
                color: AppColors.border,
                borderRadius: AppRadius.pillRadius,
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                AppSpacing.mdSmall,
                AppSpacing.sm,
                AppSpacing.sm,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: AppSearchBar(
                      controller: _controller,
                      autofocus: true,
                      hintText: 'Nhập tên bảo tàng, quán cà phê, biển...',
                      onChanged: _onChanged,
                      onSubmitted: _search,
                      onClear: () {
                        _controller.clear();
                        _onChanged('');
                      },
                    ),
                  ),
                  const SizedBox(width: AppSpacing.xs),
                  IconButton(
                    tooltip: 'Đóng',
                    icon: const Icon(Icons.close_rounded),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
            ),
            if (_controller.text.trim().isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.xs,
                ),
                child: Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: () => _handoffToMap(_controller.text),
                    icon: const Icon(Icons.map_outlined, size: 16),
                    label: const Text('Tìm kết quả trên Bản đồ'),
                  ),
                ),
              ),
            const Divider(),
            Expanded(
              child: _buildBody(userPos),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBody(dynamic userPos) {
    if (_submittedQuery.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Gợi ý tìm kiếm nhanh', style: AppTypography.h3),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                for (final term in ['Cà phê', 'Bảo tàng', 'Biển Mỹ Khê', 'Phở'])
                  ActionChip(
                    label: Text(term),
                    onPressed: () {
                      _controller.text = term;
                      _search(term);
                    },
                  ),
              ],
            ),
          ],
        ),
      );
    }
    if (_loading) {
      return const AppLoading(message: 'Đang tìm địa điểm xác minh...');
    }
    if (_error != null) {
      return AppErrorState(
        message: _error!,
        onRetry: () => _search(_submittedQuery),
      );
    }
    if (_results.isEmpty) {
      return AppEmptyState(
        icon: Icons.search_off_rounded,
        title: 'Không tìm thấy kết quả',
        description:
            'Chưa có địa điểm xác minh phù hợp với "$_submittedQuery".',
        actionLabel: 'Thử tìm trên Bản đồ',
        onAction: () => _handoffToMap(_submittedQuery),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: _results.length + 1,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (ctx, idx) {
        if (idx == _results.length) {
          return AppButton(
            text: 'Mở tất cả trên Bản đồ',
            variant: AppButtonVariant.tonal,
            icon: Icons.map_outlined,
            onPressed: () => _handoffToMap(_submittedQuery),
          );
        }
        final place = _results[idx];
        return HomeVerifiedPlaceTile(
          place: place,
          userPosition: userPos,
          onTap: () {
            Navigator.of(context).pop();
            context.push('/places/${place.id}');
          },
        );
      },
    );
  }
}
