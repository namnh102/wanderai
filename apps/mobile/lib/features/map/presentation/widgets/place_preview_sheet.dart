import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_badge.dart';
import '../../../../core/widgets/rating_view.dart';
import '../../../../core/widgets/responsive_wrapper.dart';
import '../../data/place_model.dart';

/// Bottom sheet showing place preview when a marker is tapped.
/// Follows GoMate Design Spec Section 6.8 & Rating Integrity DUX-02.
class PlacePreviewSheet extends StatelessWidget {
  final PlaceModel place;
  final VoidCallback onClose;

  const PlacePreviewSheet({
    super.key,
    required this.place,
    required this.onClose,
  });

  @override
  Widget build(BuildContext context) {
    final bottomPadding = MediaQuery.of(context).padding.bottom;
    final catColor = AppColors.forCategory(place.categoryName);

    return ResponsiveWrapper(
      maxWidth: 540.0,
      child: Container(
        padding: EdgeInsets.only(
          left: AppSpacing.md,
          right: AppSpacing.md,
          top: AppSpacing.mdSmall,
          bottom: bottomPadding + AppSpacing.mdSmall,
        ),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: AppRadius.sheetRadius,
          border: Border.all(color: AppColors.border, width: 1),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.12),
              blurRadius: 16,
              offset: const Offset(0, -4),
            ),
          ],
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Handle bar
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: AppSpacing.mdSmall),

            // Header row
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Category icon
                Container(
                  padding: const EdgeInsets.all(AppSpacing.sm),
                  decoration: BoxDecoration(
                    color: catColor.withValues(alpha: 0.12),
                    borderRadius: AppRadius.smRadius,
                  ),
                  child: Icon(
                    _categoryIcon(place.categoryName),
                    color: catColor,
                    size: 24,
                  ),
                ),
                const SizedBox(width: AppSpacing.mdSmall),

                // Name and category
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        place.name,
                        style: AppTypography.h3.copyWith(fontSize: 16),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 2),
                      if (place.categoryName != null)
                        Text(
                          _categoryLabel(place.categoryName!),
                          style: AppTypography.bodyS.copyWith(
                            color: catColor,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                    ],
                  ),
                ),

                // Close button
                IconButton(
                  onPressed: onClose,
                  icon: const Icon(Icons.close, size: 20),
                  color: AppColors.textSecondary,
                  style: IconButton.styleFrom(
                    padding: const EdgeInsets.all(4),
                    minimumSize: const Size(32, 32),
                  ),
                ),
              ],
            ),

            const SizedBox(height: AppSpacing.mdSmall),

            // Info chips row
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.xs,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                // Honest Rating
                RatingView(
                  rating: place.rating,
                  reviewCount: place.reviewCount,
                ),

                // Distance
                if (place.distanceKm != null)
                  _InfoChip(
                    icon: Icons.near_me,
                    label: place.distanceKm! < 1
                        ? '${(place.distanceKm! * 1000).toInt()}m'
                        : '${place.distanceKm!.toStringAsFixed(1)} km',
                    color: AppColors.primary,
                  ),

                // Verified badge
                if (place.isVerified) AppBadge.verified(),

                // Destination
                if (place.destinationName != null)
                  _InfoChip(
                    icon: Icons.location_city,
                    label: place.destinationName!,
                    color: AppColors.textSecondary,
                  ),
              ],
            ),

            // Address
            if (place.address != null && place.address!.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(
                    Icons.location_on_outlined,
                    size: 15,
                    color: AppColors.textTertiary,
                  ),
                  const SizedBox(width: AppSpacing.xs),
                  Expanded(
                    child: Text(
                      place.address!,
                      style: AppTypography.bodyS,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ],

            const SizedBox(height: AppSpacing.sm),

            // Coordinates
            if (place.hasCoordinates)
              Text(
                '${place.latitude!.toStringAsFixed(5)}, ${place.longitude!.toStringAsFixed(5)}',
                style: AppTypography.bodyS.copyWith(
                  color: AppColors.textTertiary,
                  fontSize: 11,
                  fontFamily: 'monospace',
                ),
              ),
          ],
        ),
      ),
    );
  }

  IconData _categoryIcon(String? category) {
    switch (category?.toLowerCase()) {
      case 'attraction': return Icons.attractions;
      case 'restaurant': return Icons.restaurant;
      case 'hotel': return Icons.hotel;
      case 'temple': case 'pagoda': return Icons.temple_buddhist;
      case 'beach': return Icons.beach_access;
      case 'museum': case 'culture': return Icons.museum;
      case 'park': case 'nature': return Icons.park;
      case 'market': return Icons.store;
      case 'cafe': return Icons.local_cafe;
      default: return Icons.place;
    }
  }

  String _categoryLabel(String category) {
    switch (category.toLowerCase()) {
      case 'attraction': return 'Tham quan';
      case 'restaurant': return 'Nhà hàng';
      case 'hotel': return 'Khách sạn';
      case 'temple': case 'pagoda': return 'Đền/Chùa';
      case 'beach': return 'Biển';
      case 'museum': return 'Bảo tàng';
      case 'park': return 'Công viên';
      case 'market': return 'Chợ';
      case 'cafe': return 'Cà phê';
      case 'entertainment': return 'Giải trí';
      case 'culture': return 'Văn hóa';
      case 'nature': return 'Thiên nhiên';
      default: return category;
    }
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _InfoChip({
    required this.icon,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: AppSpacing.xs),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: AppRadius.smRadius,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: color),
          const SizedBox(width: AppSpacing.xs),
          Text(
            label,
            style: AppTypography.label.copyWith(
              fontSize: 11,
              color: color,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
