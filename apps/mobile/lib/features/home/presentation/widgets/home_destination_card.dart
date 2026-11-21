import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/rating_view.dart';
import '../../data/home_models.dart';

/// Editorial UX V2 destination card.
/// Shows factual provenance/place counts and never fabricates ratings.
class HomeDestinationCard extends StatelessWidget {
  final HomeDestinationItem destination;
  final VoidCallback onTap;

  const HomeDestinationCard({
    super.key,
    required this.destination,
    required this.onTap,
  });

  List<Color> _regionGradient() {
    switch (destination.region?.toLowerCase()) {
      case 'north':
        return const [AppColors.primaryDeep, Color(0xFF1D4E5A)];
      case 'central':
        return const [AppColors.primary, Color(0xFF0B524C)];
      case 'south':
        return const [Color(0xFF9A3412), AppColors.accentCoral];
      default:
        return const [AppColors.primaryDeep, AppColors.primary];
    }
  }

  IconData _regionIcon() {
    switch (destination.region?.toLowerCase()) {
      case 'north':
        return Icons.terrain_rounded;
      case 'central':
        return Icons.temple_buddhist_rounded;
      case 'south':
        return Icons.beach_access_rounded;
      default:
        return Icons.explore_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    final gradient = _regionGradient();

    return AppCard(
      padding: EdgeInsets.zero,
      onTap: onTap,
      elevated: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            height: 92,
            width: double.infinity,
            padding: const EdgeInsets.all(AppSpacing.sm),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: gradient,
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: Stack(
              children: [
                Positioned(
                  right: -6,
                  bottom: -8,
                  child: Icon(
                    _regionIcon(),
                    size: 62,
                    color: Colors.white.withValues(alpha: 0.16),
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Flexible(
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 7,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.2),
                              borderRadius: AppRadius.smRadius,
                            ),
                            child: Text(
                              destination.regionLabel,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.w600,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ),
                        if (destination.isPopular) ...[
                          const SizedBox(width: 4),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 7,
                              vertical: 3,
                            ),
                            decoration: const BoxDecoration(
                              color: AppColors.accentCoral,
                              borderRadius: AppRadius.pillRadius,
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
                        ],
                      ],
                    ),
                    if (destination.placeCount > 0)
                      Text(
                        '${destination.placeCount} địa điểm',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.92),
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                  ],
                ),
              ],
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.mdSmall),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        destination.name,
                        style: AppTypography.h3.copyWith(fontSize: 15),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        destination.province.isNotEmpty
                            ? destination.province
                            : destination.regionLabel,
                        style: AppTypography.caption,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                  RatingView(
                    rating: destination.rating,
                    reviewCount: destination.reviewCount,
                    iconSize: 13,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
