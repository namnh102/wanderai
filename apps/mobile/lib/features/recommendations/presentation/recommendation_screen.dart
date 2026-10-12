import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/app_chip.dart';
import '../../../core/widgets/app_empty_state.dart';
import '../../../core/widgets/app_error_state.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../../profile/data/profile_models.dart';
import '../data/recommendation_models.dart';
import '../providers/recommendation_provider.dart';

/// "Gợi ý cho bạn": personalised places from the real REC-A runtime
/// (Flutter -> NestJS -> FastAPI -> REC-A). No rating is shown because the
/// recommendation response carries none; Place Detail shows the real rating state.
class RecommendationScreen extends ConsumerStatefulWidget {
  const RecommendationScreen({super.key});

  @override
  ConsumerState<RecommendationScreen> createState() => _RecommendationScreenState();
}

class _RecommendationScreenState extends ConsumerState<RecommendationScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (!mounted) return;
      final notifier = ref.read(recommendationProvider.notifier);
      if (ref.read(recommendationProvider).status == RecommendationStatus.initial) {
        notifier.load();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(recommendationProvider);
    final notifier = ref.read(recommendationProvider.notifier);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Gợi ý cho bạn'),
        actions: [
          IconButton(
            key: const Key('reco_edit_preferences'),
            icon: const Icon(Icons.tune_outlined),
            tooltip: 'Sở thích du lịch',
            color: AppColors.primary,
            onPressed: () => context.push('/profile/preferences'),
          ),
        ],
      ),
      body: ResponsiveWrapper(
        maxWidth: 800.0,
        child: Column(
          children: [
            _DestinationSelector(
              selected: state.destination,
              onSelected: notifier.selectDestination,
            ),
            Expanded(child: _buildBody(state, notifier)),
          ],
        ),
      ),
    );
  }

  Widget _buildBody(RecommendationState state, RecommendationNotifier notifier) {
    switch (state.status) {
      case RecommendationStatus.initial:
      case RecommendationStatus.loading:
        return const AppLoading(message: 'Đang tìm gợi ý phù hợp...');
      case RecommendationStatus.error:
        return AppErrorState(
          message: state.errorMessage ?? 'Không thể tải gợi ý. Vui lòng thử lại.',
          onRetry: notifier.retry,
        );
      case RecommendationStatus.empty:
        return AppEmptyState(
          icon: Icons.travel_explore_outlined,
          title: 'Chưa có gợi ý',
          description: 'Chưa có địa điểm phù hợp ở ${state.destination.label}.',
          actionLabel: 'Cập nhật sở thích',
          onAction: () => context.push('/profile/preferences'),
        );
      case RecommendationStatus.success:
        return _ResultList(result: state.result!, destination: state.destination);
    }
  }
}

class _DestinationSelector extends StatelessWidget {
  final RecommendationDestination selected;
  final ValueChanged<RecommendationDestination> onSelected;

  const _DestinationSelector({required this.selected, required this.onSelected});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.md, AppSpacing.md, AppSpacing.sm),
      child: Wrap(
        spacing: AppSpacing.sm,
        runSpacing: AppSpacing.sm,
        children: [
          for (final d in RecommendationDestination.values)
            AppChip(
              key: Key('reco_destination_${d.slug}'),
              label: d.label,
              icon: Icons.place_outlined,
              isSelected: d == selected,
              onTap: () => onSelected(d),
            ),
        ],
      ),
    );
  }
}

class _ResultList extends StatelessWidget {
  final RecommendationResult result;
  final RecommendationDestination destination;

  const _ResultList({required this.result, required this.destination});

  @override
  Widget build(BuildContext context) {
    final items = result.recommendations;
    final cold = result.metadata.coldStart;
    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.xl),
      itemCount: items.length + (cold ? 1 : 0),
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        if (cold && index == 0) return const _ColdStartNotice();
        final item = items[index - (cold ? 1 : 0)];
        return _RecommendationCard(item: item);
      },
    );
  }
}

/// Cold start is a valid success: the user simply has no canonical interests yet.
class _ColdStartNotice extends StatelessWidget {
  const _ColdStartNotice();

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const Key('reco_cold_start_notice'),
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.primaryContainer.withValues(alpha: 0.6),
        borderRadius: AppRadius.cardRadius,
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline, color: AppColors.primary),
          const SizedBox(width: AppSpacing.sm),
          const Expanded(
            child: Text(
              'Bạn chưa chọn sở thích nên đây là gợi ý đa dạng. Chọn sở thích để nhận gợi ý cá nhân hóa.',
              style: AppTypography.bodyS,
            ),
          ),
          TextButton(
            onPressed: () => context.push('/profile/preferences'),
            child: const Text('Chọn'),
          ),
        ],
      ),
    );
  }
}

class _RecommendationCard extends StatelessWidget {
  final RecommendedPlace item;

  const _RecommendationCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final interests = item.matchedInterests.isNotEmpty
        ? item.matchedInterests
        : item.explanation.matchedInterests;
    return AppCard(
      key: Key('reco_item_${item.placeId}'),
      onTap: () => context.push('/places/${item.placeId}'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  item.name,
                  style: AppTypography.h3,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const Icon(Icons.chevron_right, color: AppColors.textSecondary),
            ],
          ),
          const SizedBox(height: 2),
          Text(categoryLabel(item.category), style: AppTypography.bodyS),
          if (item.explanation.text.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(item.explanation.text, style: AppTypography.bodyM),
          ],
          if (interests.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                for (final key in interests)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: const BoxDecoration(
                      color: AppColors.primaryContainer,
                      borderRadius: AppRadius.smRadius,
                    ),
                    child: Text(
                      interestLabel(key),
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: AppColors.onPrimaryContainer,
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// Display label for a canonical interest key (falls back to the raw key).
String interestLabel(String key) {
  for (final i in kCanonicalInterests) {
    if (i.key == key) return i.label;
  }
  return key;
}

/// Display label for a POI category slug (falls back to the raw value).
String categoryLabel(String category) {
  switch (category.toLowerCase()) {
    case 'attraction':
      return 'Tham quan';
    case 'restaurant':
      return 'Nhà hàng';
    case 'hotel':
      return 'Khách sạn';
    case 'temple':
    case 'pagoda':
      return 'Đền/Chùa';
    case 'beach':
      return 'Biển';
    case 'museum':
      return 'Bảo tàng';
    case 'park':
      return 'Công viên';
    case 'market':
      return 'Chợ';
    case 'cafe':
      return 'Cà phê';
    case 'entertainment':
      return 'Giải trí';
    case 'culture':
      return 'Văn hóa';
    case 'nature':
      return 'Thiên nhiên';
    default:
      return category;
  }
}
