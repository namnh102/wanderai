import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/router/app_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_badge.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/app_chip.dart';
import '../../../core/widgets/app_empty_state.dart';
import '../../../core/widgets/app_error_state.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/app_search_bar.dart';
import '../../../core/widgets/app_section_header.dart';
import '../../../core/widgets/app_skeleton.dart';
import '../../../core/widgets/app_state_banner.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../../ai_chat/providers/chat_provider.dart';
import '../../auth/providers/auth_provider.dart';
import '../../location/providers/user_location_provider.dart';
import '../../map/data/place_model.dart';
import '../../places/presentation/place_detail_screen.dart';
import '../data/home_models.dart';
import '../providers/home_provider.dart';
import 'widgets/destination_places_sheet.dart';
import 'widgets/home_destination_card.dart';
import 'widgets/home_search_sheet.dart';
import 'widgets/home_verified_place_tile.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() async {
      if (!mounted) return;
      await ref.read(userLocationProvider.notifier).refreshIfPermitted();
      if (!mounted) return;
      final pos = ref.read(userLocationProvider).position;
      if (pos != null) {
        await ref.read(homeProvider.notifier).loadNearby(pos);
      }
    });
  }

  Future<void> _onRefresh() async {
    final pos = ref.read(userLocationProvider).position;
    await ref.read(homeProvider.notifier).load(userPosition: pos);
  }

  Future<void> _onEnableLocation() async {
    final pos = await ref.read(userLocationProvider.notifier).request();
    if (!mounted) return;
    if (pos != null) {
      await ref.read(homeProvider.notifier).loadNearby(pos);
    }
  }

  void _openWandyWithPrompt(String prompt) {
    ref.read(pendingChatPromptProvider.notifier).state = prompt;
    context.go('/ai');
  }

  @override
  Widget build(BuildContext context) {
    final homeState = ref.watch(homeProvider);
    final locationState = ref.watch(userLocationProvider);
    final isGuest = ref.watch(guestBrowseModeProvider);
    final authStatus = ref.watch(authProvider.select((s) => s.status));
    final showGuestAuthAction =
        isGuest && authStatus != AuthStatus.authenticated;

    ref.listen<UserLocationState>(userLocationProvider, (prev, next) {
      if (next.position != null && prev?.position != next.position) {
        ref.read(homeProvider.notifier).loadNearby(next.position!);
      }
    });

    return Scaffold(
      backgroundColor: AppColors.warmBackground,
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              width: 32,
              height: 32,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [AppColors.primary, AppColors.primaryDeep],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: AppRadius.smRadius,
              ),
              child: const Center(
                child: Icon(
                  Icons.explore_rounded,
                  color: Colors.white,
                  size: 18,
                ),
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Text(
              'GoMate',
              style: AppTypography.h2.copyWith(
                fontWeight: FontWeight.w800,
                color: AppColors.primaryDeep,
              ),
            ),
          ],
        ),
        actions: showGuestAuthAction
            ? [
                TextButton.icon(
                  key: const Key('home_login_button'),
                  onPressed: () => context.go('/login'),
                  icon: const Icon(Icons.login_rounded, size: 18),
                  label: const Text('Đăng nhập'),
                ),
              ]
            : [
                IconButton(
                  key: const Key('home_preferences_button'),
                  icon: const Icon(Icons.tune_outlined),
                  tooltip: 'Sở thích du lịch',
                  color: AppColors.primary,
                  onPressed: () => context.push('/profile/preferences'),
                ),
                IconButton(
                  key: const Key('home_logout_button'),
                  icon: const Icon(Icons.logout_rounded),
                  tooltip: 'Đăng xuất',
                  color: AppColors.textSecondary,
                  onPressed: () => ref.read(authProvider.notifier).logout(),
                ),
              ],
      ),
      body: ResponsiveWrapper(
        maxWidth: 1040.0,
        child: _buildBody(context, homeState, locationState),
      ),
    );
  }

  Widget _buildBody(
    BuildContext context,
    HomeState homeState,
    UserLocationState locationState,
  ) {
    if (homeState.isLoading && homeState.destinations.isEmpty) {
      return const _HomeLoadingSkeleton();
    }

    if (homeState.errorMessage != null && homeState.destinations.isEmpty) {
      return AppErrorState(
        title: homeState.isOfflineError
            ? 'Không có kết nối mạng'
            : 'Không thể tải dữ liệu',
        message: homeState.errorMessage!,
        onRetry: _onRefresh,
      );
    }

    if (homeState.destinations.isEmpty && homeState.featuredPlaces.isEmpty) {
      return AppEmptyState(
        title: 'Chưa có điểm đến',
        description: 'Chưa có điểm đến nào trong hệ thống.',
        actionLabel: 'Tải lại',
        onAction: _onRefresh,
      );
    }

    final filteredDestinations = homeState.filteredDestinations;
    final textScale = MediaQuery.textScalerOf(context).scale(1.0);
    final double cardExtent = textScale > 1.15 ? 248.0 : 216.0;
    final double carouselHeight = textScale > 1.15 ? 240.0 : 210.0;

    return RefreshIndicator(
      onRefresh: _onRefresh,
      color: AppColors.primary,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth >= 680;
          final gridColumns = constraints.maxWidth >= 960
              ? 4
              : (constraints.maxWidth >= 680 ? 3 : 2);
          final showGrid = isWide || homeState.showAllDestinations;
          final canToggleAll = isWide
              ? filteredDestinations.length > 8
              : filteredDestinations.length > 4;
          final visibleDestinations = (isWide && !homeState.showAllDestinations)
              ? filteredDestinations.take(8).toList()
              : filteredDestinations;

          return CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: [
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md,
                    AppSpacing.md,
                    AppSpacing.md,
                    AppSpacing.sm,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (homeState.partialBannerMessage != null) ...[
                        AppStateBanner(
                          message: homeState.partialBannerMessage!,
                          tone: homeState.isOfflineError
                              ? AppStateBannerTone.warning
                              : AppStateBannerTone.info,
                          actionLabel: 'Thử lại',
                          onAction: _onRefresh,
                        ),
                        const SizedBox(height: AppSpacing.md),
                      ],
                      _GreetingHeader(displayName: homeState.userDisplayName),
                      const SizedBox(height: AppSpacing.md),
                      AppSearchBar(
                        key: const Key('home_search_bar'),
                        readOnly: true,
                        hintText: 'Tìm địa điểm, món ăn, bảo tàng, cà phê...',
                        onTap: () => showHomeSearchSheet(context),
                        trailing: const Icon(
                          Icons.tune_rounded,
                          size: 18,
                          color: AppColors.textTertiary,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      _WandyHeroCard(
                        onTapCard: () => context.go('/ai'),
                        onTapPrompt: _openWandyWithPrompt,
                      ),
                      const SizedBox(height: AppSpacing.mdSmall),
                      _RecommendationEntryCard(
                        interests: homeState.userInterests,
                        onTap: () => context.push('/recommendations'),
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      AppSectionHeader(
                        title: 'Điểm đến nổi bật',
                        countLabel: '${filteredDestinations.length} điểm đến',
                        actionLabel: canToggleAll
                            ? (homeState.showAllDestinations
                                ? 'Thu gọn'
                                : 'Xem tất cả →')
                            : null,
                        onAction: canToggleAll
                            ? () => ref
                                .read(homeProvider.notifier)
                                .toggleShowAllDestinations()
                            : null,
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Wrap(
                        spacing: AppSpacing.sm,
                        runSpacing: AppSpacing.sm,
                        children: [
                          for (final region in HomeRegionFilter.values)
                            AppChip(
                              key: Key('home_region_${region.name}'),
                              label: region.label,
                              isSelected: homeState.selectedRegion == region,
                              onTap: () => ref
                                  .read(homeProvider.notifier)
                                  .setRegion(region),
                            ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.mdSmall),
                    ],
                  ),
                ),
              ),

              if (visibleDestinations.isEmpty)
                const SliverToBoxAdapter(
                  child: Padding(
                    padding: EdgeInsets.symmetric(horizontal: AppSpacing.md),
                    child: AppStateBanner(
                      message: 'Chưa có điểm đến nào trong khu vực đã chọn.',
                      tone: AppStateBannerTone.info,
                    ),
                  ),
                )
              else if (!showGrid)
                SliverToBoxAdapter(
                  child: SizedBox(
                    height: carouselHeight,
                    child: ListView.separated(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.md,
                      ),
                      scrollDirection: Axis.horizontal,
                      itemCount: visibleDestinations.length,
                      separatorBuilder: (_, __) =>
                          const SizedBox(width: AppSpacing.mdSmall),
                      itemBuilder: (ctx, index) {
                        final d = visibleDestinations[index];
                        return SizedBox(
                          width: 162,
                          child: HomeDestinationCard(
                            key: Key('home_dest_${d.slug}'),
                            destination: d,
                            onTap: () => showDestinationPlacesSheet(
                              context,
                              destination: d,
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                )
              else
                SliverPadding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.md,
                  ),
                  sliver: SliverGrid(
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: gridColumns,
                      crossAxisSpacing: AppSpacing.mdSmall,
                      mainAxisSpacing: AppSpacing.mdSmall,
                      mainAxisExtent: cardExtent,
                    ),
                    delegate: SliverChildBuilderDelegate(
                      (context, index) {
                        final d = visibleDestinations[index];
                        return HomeDestinationCard(
                          key: Key('home_dest_${d.slug}'),
                          destination: d,
                          onTap: () => showDestinationPlacesSheet(
                            context,
                            destination: d,
                          ),
                        );
                      },
                      childCount: visibleDestinations.length,
                    ),
                  ),
                ),

              // ─── Trending & Enriched Verified Places ───
              if (homeState.trendingPlaces.isNotEmpty)
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.only(top: AppSpacing.lg),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: AppSpacing.md,
                          ),
                          child: AppSectionHeader(
                            title: 'Nổi bật & Đầy đủ dữ liệu',
                            subtitle:
                                'Xếp hạng theo dữ liệu OSM/Wikimedia & đánh giá thật',
                            actionLabel: 'Bản đồ →',
                            onAction: () => context.go('/map'),
                          ),
                        ),
                        const SizedBox(height: AppSpacing.sm),
                        SizedBox(
                          height: 176,
                          child: ListView.separated(
                            padding: const EdgeInsets.symmetric(
                              horizontal: AppSpacing.md,
                            ),
                            scrollDirection: Axis.horizontal,
                            itemCount: homeState.trendingPlaces.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(width: AppSpacing.mdSmall),
                            itemBuilder: (_, idx) {
                              final p = homeState.trendingPlaces[idx];
                              final color =
                                  AppColors.forCategory(p.categoryName);
                              return SizedBox(
                                width: 224,
                                child: AppCard(
                                  key: Key('home_trending_${p.id}'),
                                  padding: EdgeInsets.zero,
                                  onTap: () => context.push('/places/${p.id}'),
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      ClipRRect(
                                        borderRadius:
                                            const BorderRadius.vertical(
                                          top: Radius.circular(16),
                                        ),
                                        child: Container(
                                          height: 98,
                                          width: double.infinity,
                                          color: color.withValues(alpha: 0.14),
                                          child: p.coverImage != null &&
                                                  p.coverImage!
                                                      .startsWith('http')
                                              ? Image.network(
                                                  p.coverImage!,
                                                  fit: BoxFit.cover,
                                                  errorBuilder: (_, __, ___) =>
                                                      Icon(
                                                    placeCategoryIcon(
                                                        p.categoryName),
                                                    color: color,
                                                    size: 32,
                                                  ),
                                                )
                                              : Icon(
                                                  placeCategoryIcon(
                                                      p.categoryName),
                                                  color: color,
                                                  size: 32,
                                                ),
                                        ),
                                      ),
                                      Padding(
                                        padding:
                                            const EdgeInsets.all(AppSpacing.sm),
                                        child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              p.name,
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              style:
                                                  AppTypography.label.copyWith(
                                                fontWeight: FontWeight.w700,
                                              ),
                                            ),
                                            const SizedBox(height: 2),
                                            Text(
                                              [
                                                if (p.categoryName != null)
                                                  placeCategoryLabel(
                                                      p.categoryName!),
                                                if (p.destinationName != null)
                                                  p.destinationName!,
                                              ].join(' · '),
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              style: AppTypography.bodyS,
                                            ),
                                          ],
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              );
                            },
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

              // ─── Nearby & Verified Places Section ───
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(
                    AppSpacing.md,
                    AppSpacing.lg,
                    AppSpacing.md,
                    AppSpacing.xxl,
                  ),
                  child: _buildPlacesDiscoverySection(
                    context,
                    homeState,
                    locationState,
                    isWide,
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }

  Widget _buildPlacesDiscoverySection(
    BuildContext context,
    HomeState homeState,
    UserLocationState locationState,
    bool isWide,
  ) {
    final bool hasGps = locationState.position != null;
    final List<PlaceModel> placesToShow =
        hasGps ? homeState.nearbyPlaces : homeState.featuredPlaces;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AppSectionHeader(
          title: hasGps ? 'Địa điểm gần bạn' : 'Địa điểm đã xác minh',
          subtitle: hasGps
              ? 'Dữ liệu OpenStreetMap quanh vị trí hiện tại'
              : 'Nguồn OpenStreetMap đã qua kiểm chứng',
          actionLabel: 'Mở Bản đồ →',
          onAction: () => context.go('/map'),
        ),
        const SizedBox(height: AppSpacing.sm),
        if (!hasGps) ...[
          _LocationPromptCard(
            locationState: locationState,
            onEnableLocation: _onEnableLocation,
          ),
          const SizedBox(height: AppSpacing.md),
        ] else if (locationState.label != null) ...[
          AppBadge(
            label: locationState.label!,
            icon: Icons.my_location_rounded,
            color: AppColors.primary,
            backgroundColor: AppColors.primaryContainer,
          ),
          const SizedBox(height: AppSpacing.mdSmall),
        ],
        if (hasGps && homeState.isNearbyLoading)
          const AppLoading(
            isCompact: true,
            message: 'Đang tìm địa điểm quanh bạn...',
          )
        else if (placesToShow.isEmpty)
          AppStateBanner(
            message: hasGps
                ? 'Chưa tìm thấy địa điểm xác minh nào trong bán kính 10 km quanh bạn.'
                : 'Chưa tải được danh sách địa điểm xác minh.',
            actionLabel: 'Xem bản đồ',
            onAction: () => context.go('/map'),
          )
        else if (isWide)
          Wrap(
            spacing: AppSpacing.mdSmall,
            runSpacing: AppSpacing.mdSmall,
            children: [
              for (final p in placesToShow.take(6))
                SizedBox(
                  width: 480,
                  child: HomeVerifiedPlaceTile(
                    key: Key('home_place_${p.id}'),
                    place: p,
                    userPosition: locationState.position,
                    onTap: () => context.push('/places/${p.id}'),
                  ),
                ),
            ],
          )
        else
          Column(
            children: [
              for (final p in placesToShow.take(5)) ...[
                HomeVerifiedPlaceTile(
                  key: Key('home_place_${p.id}'),
                  place: p,
                  userPosition: locationState.position,
                  onTap: () => context.push('/places/${p.id}'),
                ),
                const SizedBox(height: AppSpacing.sm),
              ],
            ],
          ),
      ],
    );
  }
}

class _GreetingHeader extends StatelessWidget {
  final String? displayName;

  const _GreetingHeader({required this.displayName});

  @override
  Widget build(BuildContext context) {
    final greeting = (displayName != null && displayName!.isNotEmpty)
        ? 'Xin chào, $displayName 👋'
        : 'Xin chào bạn 👋';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          greeting,
          style: AppTypography.h1.copyWith(
            fontSize: 23,
            fontWeight: FontWeight.w800,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        Text(
          'Hôm nay bạn muốn khám phá miền nào của Việt Nam?',
          style: AppTypography.bodyM.copyWith(color: AppColors.textSecondary),
        ),
      ],
    );
  }
}

class _WandyHeroCard extends StatelessWidget {
  final VoidCallback onTapCard;
  final ValueChanged<String> onTapPrompt;

  const _WandyHeroCard({
    required this.onTapCard,
    required this.onTapPrompt,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: AppRadius.heroRadius,
        gradient: const LinearGradient(
          colors: [AppColors.primaryDeep, AppColors.primary],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withValues(alpha: 0.2),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        borderRadius: AppRadius.heroRadius,
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTapCard,
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.16),
                        borderRadius: AppRadius.mdRadius,
                      ),
                      child: const Icon(
                        Icons.auto_awesome,
                        color: Colors.white,
                        size: 22,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.mdSmall),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Wandy AI Copilot',
                            style: AppTypography.h3.copyWith(
                              color: Colors.white,
                              fontSize: 16.5,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'Hỏi đáp địa điểm OpenStreetMap & gợi ý lịch trình',
                            style: AppTypography.bodyS.copyWith(
                              color: Colors.white.withValues(alpha: 0.88),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(
                      Icons.chevron_right_rounded,
                      color: Colors.white,
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.mdSmall),
                Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.sm,
                  children: [
                    _HeroPromptChip(
                      label: '✦ Lịch trình Đà Nẵng 3N2Đ',
                      onTap: () => onTapPrompt(
                        'Gợi ý lịch trình khám phá Đà Nẵng 3 ngày 2 đêm',
                      ),
                    ),
                    _HeroPromptChip(
                      label: '✦ Văn hóa Hà Nội',
                      onTap: () => onTapPrompt(
                        'Gợi ý các địa điểm văn hóa nổi bật tại Hà Nội',
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _HeroPromptChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _HeroPromptChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.14),
      shape: RoundedRectangleBorder(
        borderRadius: AppRadius.pillRadius,
        side: BorderSide(color: Colors.white.withValues(alpha: 0.25)),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.mdSmall,
            vertical: 7,
          ),
          child: Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ),
    );
  }
}

/// Entry point to the personalised REC-A recommendations (reachable from Khám phá).
class _RecommendationEntryCard extends StatelessWidget {
  final List<String> interests;
  final VoidCallback onTap;

  const _RecommendationEntryCard({
    required this.interests,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final String subtitle;
    if (interests.isNotEmpty) {
      final labels = interests.take(2).map(interestDisplayLabel).join(', ');
      subtitle = interests.length > 2
          ? 'Theo sở thích của bạn: $labels...'
          : 'Theo sở thích của bạn: $labels';
    } else {
      subtitle = 'Địa điểm phù hợp với phong cách du lịch của bạn';
    }

    return AppCard(
      key: const Key('home_recommendation_entry'),
      backgroundColor: AppColors.warmSurface,
      onTap: onTap,
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: const BoxDecoration(
              color: AppColors.primaryContainer,
              borderRadius: AppRadius.mdRadius,
            ),
            child: const Icon(
              Icons.recommend_outlined,
              color: AppColors.primary,
            ),
          ),
          const SizedBox(width: AppSpacing.mdSmall),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Gợi ý cho bạn',
                  style: AppTypography.h3.copyWith(fontSize: 16),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: AppTypography.caption,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded,
              color: AppColors.textSecondary),
        ],
      ),
    );
  }
}

class _LocationPromptCard extends StatelessWidget {
  final UserLocationState locationState;
  final VoidCallback onEnableLocation;

  const _LocationPromptCard({
    required this.locationState,
    required this.onEnableLocation,
  });

  @override
  Widget build(BuildContext context) {
    final isRequesting = locationState.status == UserLocationStatus.requesting;
    final isDenied = locationState.status == UserLocationStatus.denied;

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadius.cardRadius,
        border: Border.all(
          color: AppColors.primary.withValues(alpha: 0.25),
          width: 1,
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: const BoxDecoration(
              color: AppColors.surfaceContainer,
              shape: BoxShape.circle,
            ),
            child: Icon(
              isDenied
                  ? Icons.location_off_outlined
                  : Icons.my_location_outlined,
              color: AppColors.primary,
              size: 20,
            ),
          ),
          const SizedBox(width: AppSpacing.mdSmall),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isDenied
                      ? 'Quyền vị trí chưa được bật'
                      : 'Khám phá địa điểm gần bạn',
                  style: AppTypography.label.copyWith(fontSize: 13.5),
                ),
                const SizedBox(height: 2),
                Text(
                  isDenied
                      ? 'Bật quyền định vị để xem khoảng cách thực tế quanh bạn.'
                      : 'Chạm “Bật vị trí” để tính khoảng cách thực tế tới các điểm xác minh.',
                  style: AppTypography.caption,
                ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          AppButton(
            text: 'Bật vị trí',
            variant: AppButtonVariant.tonal,
            isFullWidth: false,
            isLoading: isRequesting,
            onPressed: isRequesting ? null : onEnableLocation,
          ),
        ],
      ),
    );
  }
}

class _HomeLoadingSkeleton extends StatelessWidget {
  const _HomeLoadingSkeleton();

  @override
  Widget build(BuildContext context) {
    return const SingleChildScrollView(
      padding: EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AppSkeletonBox(width: 210, height: 26),
          SizedBox(height: AppSpacing.sm),
          AppSkeletonBox(width: 280, height: 16),
          SizedBox(height: AppSpacing.md),
          AppSkeletonBox(height: 48, borderRadius: AppRadius.mdRadius),
          SizedBox(height: AppSpacing.md),
          AppSkeletonBox(height: 128, borderRadius: AppRadius.heroRadius),
          SizedBox(height: AppSpacing.mdSmall),
          AppSkeletonBox(height: 68, borderRadius: AppRadius.cardRadius),
          SizedBox(height: AppSpacing.lg),
          AppSkeletonBox(width: 170, height: 22),
          SizedBox(height: AppSpacing.mdSmall),
          SizedBox(
            height: 205,
            child: Row(
              children: [
                Expanded(child: AppSkeletonBox(height: 205)),
                SizedBox(width: AppSpacing.mdSmall),
                Expanded(child: AppSkeletonBox(height: 205)),
              ],
            ),
          ),
          SizedBox(height: AppSpacing.lg),
          AppLoading(
            isCompact: true,
            message: 'Đang tải dữ liệu khám phá...',
          ),
        ],
      ),
    );
  }
}
