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
import '../../../core/widgets/app_state_banner.dart';
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
      backgroundColor: AppColors.warmBackground,
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
        maxWidth: 960.0,
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
    return LayoutBuilder(
      builder: (context, constraints) {
        final useTwoCols = constraints.maxWidth >= 680;
        if (!useTwoCols) {
          return ListView.separated(
            padding: const EdgeInsets.fromLTRB(
                AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.xl),
            itemCount: items.length + (cold ? 1 : 0),
            separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.mdSmall),
            itemBuilder: (context, index) {
              if (cold && index == 0) return const _ColdStartNotice();
              final item = items[index - (cold ? 1 : 0)];
              return _RecommendationCard(item: item);
            },
          );
        }

        final rowCount = (items.length + 1) ~/ 2;
        return ListView.separated(
          padding: const EdgeInsets.fromLTRB(
              AppSpacing.md, AppSpacing.sm, AppSpacing.md, AppSpacing.xl),
          itemCount: rowCount + (cold ? 1 : 0),
          separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.mdSmall),
          itemBuilder: (context, index) {
            if (cold && index == 0) return const _ColdStartNotice();
            final pairIdx = index - (cold ? 1 : 0);
            final firstIdx = pairIdx * 2;
            final secondIdx = firstIdx + 1;
            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: _RecommendationCard(item: items[firstIdx])),
                const SizedBox(width: AppSpacing.mdSmall),
                Expanded(
                  child: secondIdx < items.length
                      ? _RecommendationCard(item: items[secondIdx])
                      : const SizedBox.shrink(),
                ),
              ],
            );
          },
        );
      },
    );
  }
}

/// Cold start is a valid success: the user simply has no canonical interests yet.
class _ColdStartNotice extends StatelessWidget {
  const _ColdStartNotice();

  @override
  Widget build(BuildContext context) {
    return AppStateBanner(
      key: const Key('reco_cold_start_notice'),
      tone: AppStateBannerTone.info,
      icon: Icons.auto_awesome_outlined,
      message:
          'Bạn chưa chọn sở thích nên đây là gợi ý đa dạng. Chọn sở thích để nhận gợi ý cá nhân hóa.',
      actionLabel: 'Chọn',
      onAction: () => context.push('/profile/preferences'),
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
    final catColor = AppColors.forCategory(item.category);
    return AppCard(
      key: Key('reco_item_${item.placeId}'),
      elevated: true,
      backgroundColor: AppColors.surface,
      border: const BorderSide(color: AppColors.softBorder),
      onTap: () => context.push('/places/${item.placeId}'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: catColor.withValues(alpha: 0.12),
                  borderRadius: AppRadius.mdRadius,
                ),
                child: Icon(_categoryIcon(item.category), color: catColor, size: 20),
              ),
              const SizedBox(width: AppSpacing.mdSmall),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      item.name,
                      style: AppTypography.h3.copyWith(fontSize: 16),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      categoryLabel(item.category),
                      style: AppTypography.label.copyWith(color: catColor),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.xs),
              const Icon(Icons.chevron_right, color: AppColors.textSecondary),
            ],
          ),
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

IconData _categoryIcon(String category) {
  switch (category.toLowerCase()) {
    case 'attraction':
      return Icons.attractions;
    case 'restaurant':
      return Icons.restaurant;
    case 'hotel':
      return Icons.hotel;
    case 'temple':
    case 'pagoda':
      return Icons.temple_buddhist;
    case 'beach':
      return Icons.beach_access;
    case 'museum':
    case 'culture':
      return Icons.museum;
    case 'park':
    case 'nature':
      return Icons.park;
    case 'market':
      return Icons.store;
    case 'cafe':
      return Icons.local_cafe;
    case 'entertainment':
      return Icons.celebration;
    default:
      return Icons.place;
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
