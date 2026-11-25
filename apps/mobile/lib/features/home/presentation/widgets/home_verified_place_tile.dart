import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_badge.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/rating_view.dart';
import '../../../location/domain/geo_distance.dart';
import '../../../map/data/place_model.dart';
import '../../../places/presentation/place_detail_screen.dart';

/// Compact factual place card for Home / Discover.
/// Enforces DUX-02 rating honesty and factual address/distance visibility.
class HomeVerifiedPlaceTile extends StatelessWidget {
  final PlaceModel place;
  final LatLng? userPosition;
  final VoidCallback onTap;

  const HomeVerifiedPlaceTile({
    super.key,
    required this.place,
    required this.userPosition,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final catColor = AppColors.forCategory(place.categoryName);
    final catLabel = place.categoryName != null
        ? placeCategoryLabel(place.categoryName!)
        : 'Địa điểm';
    final computedDist =
        place.distanceKm ?? distanceFromUserKm(userPosition, place.latitude, place.longitude);

    return AppCard(
      onTap: onTap,
      padding: const EdgeInsets.all(AppSpacing.mdSmall),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: AppRadius.mdRadius,
            child: Container(
              width: 56,
              height: 56,
              color: catColor.withValues(alpha: 0.12),
              child: place.coverImage != null &&
                      place.coverImage!.startsWith('http')
                  ? Image.network(
                      place.coverImage!,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Icon(
                        placeCategoryIcon(place.categoryName),
                        color: catColor,
                        size: 24,
                      ),
                    )
                  : Icon(
                      placeCategoryIcon(place.categoryName),
                      color: catColor,
                      size: 24,
                    ),
            ),
          ),
          const SizedBox(width: AppSpacing.mdSmall),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        place.name,
                        style: AppTypography.h3.copyWith(fontSize: 15),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (computedDist != null) ...[
                      const SizedBox(width: AppSpacing.xs),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 3,
                        ),
                        decoration: const BoxDecoration(
                          color: AppColors.primaryContainer,
                          borderRadius: AppRadius.pillRadius,
                        ),
                        child: Text(
                          formatDistanceKm(computedDist),
                          style: AppTypography.label.copyWith(
                            color: AppColors.onPrimaryContainer,
                            fontSize: 11,
                          ),
                        ),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 4),
                Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.xs,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      place.destinationName != null && place.destinationName!.isNotEmpty
                          ? '$catLabel · ${place.destinationName}'
                          : catLabel,
                      style: AppTypography.caption,
                    ),
                    if (place.isVerified) AppBadge.verified(),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  place.addressDisplay,
                  style: AppTypography.bodyS.copyWith(
                    color: place.hasAddress
                        ? AppColors.textSecondary
                        : AppColors.textTertiary,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 6),
                RatingView(
                  rating: place.rating,
                  reviewCount: place.reviewCount,
                  iconSize: 13,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
