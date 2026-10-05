import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:dio/dio.dart';
import 'package:go_router/go_router.dart';
import '../../../core/network/api_client.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/app_empty_state.dart';
import '../../../core/widgets/app_error_state.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/rating_view.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../../auth/providers/auth_provider.dart';

class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  List<dynamic> _destinations = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadDestinations();
  }

  Future<void> _loadDestinations() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final dio = ref.read(apiClientProvider);
      final response =
          await dio.get('/destinations', queryParameters: {'limit': 50});
      final data = response.data;
      setState(() {
        _destinations = data['data']?['items'] ?? [];
        _loading = false;
      });
    } on DioException catch (e) {
      setState(() {
        _error = 'Không thể tải dữ liệu điểm đến: ${e.message}';
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _error = 'Đã xảy ra lỗi không mong muốn: $e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(6),
              decoration: const BoxDecoration(
                color: AppColors.primaryContainer,
                borderRadius: AppRadius.smRadius,
              ),
              child: const Icon(Icons.auto_awesome, color: AppColors.primary, size: 20),
            ),
            const SizedBox(width: AppSpacing.sm),
            const Text(
              'GoMate',
              style: TextStyle(fontWeight: FontWeight.w800, color: AppColors.primary),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Đăng xuất',
            color: AppColors.textSecondary,
            onPressed: () => ref.read(authProvider.notifier).logout(),
          ),
        ],
      ),
      body: ResponsiveWrapper(
        maxWidth: 800.0,
        child: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const AppLoading(message: 'Đang tải dữ liệu khám phá...');
    }

    if (_error != null) {
      return AppErrorState(
        message: _error!,
        onRetry: _loadDestinations,
      );
    }

    if (_destinations.isEmpty) {
      return const AppEmptyState(
        title: 'Chưa có điểm đến',
        description: 'Chưa có điểm đến nào trong hệ thống.',
      );
    }

    return RefreshIndicator(
      onRefresh: _loadDestinations,
      color: AppColors.primary,
      child: CustomScrollView(
        slivers: [
          // ─── Header & Greeting ───
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
                  Text(
                    'Xin chào bạn 👋',
                    style: AppTypography.h1.copyWith(fontSize: 22),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Bạn muốn khám phá địa điểm nào hôm nay?',
                    style: AppTypography.bodyM,
                  ),
                  const SizedBox(height: AppSpacing.md),

                  // ─── Wandy AI Copilot Banner Card ───
                  _WandyAiBannerCard(
                    onTap: () => context.go('/ai'),
                  ),

                  const SizedBox(height: AppSpacing.lg),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        'Điểm đến nổi bật',
                        style: AppTypography.h2,
                      ),
                      Text(
                        '${_destinations.length} điểm đến',
                        style: AppTypography.bodyS,
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),
                ],
              ),
            ),
          ),

          // ─── Destinations Grid ───
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              0,
              AppSpacing.md,
              AppSpacing.xl,
            ),
            sliver: SliverGrid(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                crossAxisSpacing: AppSpacing.md,
                mainAxisSpacing: AppSpacing.md,
                childAspectRatio: 0.85,
              ),
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  final d = _destinations[index];
                  return _DestinationCard(destination: d);
                },
                childCount: _destinations.length,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Wandy AI banner card matching Section 6.5 of the GoMate UX specification.
class _WandyAiBannerCard extends StatelessWidget {
  final VoidCallback onTap;

  const _WandyAiBannerCard({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.primaryContainer.withValues(alpha: 0.6),
      shape: RoundedRectangleBorder(
        borderRadius: AppRadius.cardRadius,
        side: BorderSide(
          color: AppColors.primary.withValues(alpha: 0.25),
          width: 1,
        ),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.cardRadius,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: const BoxDecoration(
                  color: AppColors.primary,
                  borderRadius: AppRadius.mdRadius,
                ),
                child: const Icon(
                  Icons.auto_awesome,
                  color: Colors.white,
                  size: 24,
                ),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Wandy AI Copilot',
                      style: AppTypography.h3.copyWith(
                        color: AppColors.onPrimaryContainer,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      '“Bạn nói mong muốn, mình lo kế hoạch du lịch”',
                      style: AppTypography.bodyS.copyWith(
                        color: AppColors.onPrimaryContainer.withValues(alpha: 0.85),
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(
                Icons.chevron_right,
                color: AppColors.primary,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DestinationCard extends StatelessWidget {
  final dynamic destination;
  const _DestinationCard({required this.destination});

  @override
  Widget build(BuildContext context) {
    final name = destination['name'] ?? '';
    final province = destination['province'] ?? '';
    final rawRating = destination['rating'];
    final double? rating = rawRating != null ? (rawRating as num).toDouble() : null;
    final isPopular = destination['isPopular'] == true;

    // Generate a cohesive color from the destination name hash
    final hash = name.hashCode;
    final hue = (hash % 360).abs().toDouble();
    final headerColor = HSLColor.fromAHSL(1, hue, 0.45, 0.45).toColor();

    return AppCard(
      padding: EdgeInsets.zero,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Image / Placeholder Banner
          Container(
            height: 90,
            width: double.infinity,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [headerColor, headerColor.withValues(alpha: 0.75)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: Stack(
              children: [
                Center(
                  child: Icon(
                    Icons.landscape_rounded,
                    size: 40,
                    color: Colors.white.withValues(alpha: 0.65),
                  ),
                ),
                if (isPopular)
                  Positioned(
                    top: 8,
                    right: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                      decoration: const BoxDecoration(
                        color: AppColors.warning,
                        borderRadius: AppRadius.smRadius,
                      ),
                      child: const Text(
                        'Nổi bật',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),

          // Content
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.sm),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        name,
                        style: AppTypography.h3.copyWith(fontSize: 14),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        province,
                        style: AppTypography.bodyS,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                  // Rating handling
                  RatingView(rating: rating),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
