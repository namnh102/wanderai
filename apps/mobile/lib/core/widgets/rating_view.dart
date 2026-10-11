import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// Rating display component enforcing GoMate Data/UX Integrity Rule DUX-02.
/// Never fabricates rating or defaults to 4.5/0.0.
/// When rating is null, explicitly displays "Chưa có đánh giá".
class RatingView extends StatelessWidget {
  final double? rating;
  final int? reviewCount;
  final double iconSize;

  const RatingView({
    super.key,
    required this.rating,
    this.reviewCount,
    this.iconSize = 14.0,
  });

  @override
  Widget build(BuildContext context) {
    if (rating == null || rating == 0) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.star_border,
            size: iconSize,
            color: AppColors.textTertiary,
          ),
          const SizedBox(width: AppSpacing.xs),
          Text(
            'Chưa có đánh giá',
            style: AppTypography.bodyS.copyWith(
              color: AppColors.textTertiary,
              fontSize: iconSize - 2,
            ),
          ),
        ],
      );
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(
          Icons.star_rounded,
          size: iconSize + 2,
          color: Colors.amber,
        ),
        const SizedBox(width: 2),
        Text(
          rating!.toStringAsFixed(1),
          style: AppTypography.label.copyWith(
            fontWeight: FontWeight.w700,
            fontSize: iconSize - 1,
            color: AppColors.textPrimary,
          ),
        ),
        if (reviewCount != null && reviewCount! > 0) ...[
          const SizedBox(width: 4),
          Text(
            '($reviewCount)',
            style: AppTypography.bodyS.copyWith(
              fontSize: iconSize - 2,
              color: AppColors.textSecondary,
            ),
          ),
        ],
      ],
    );
  }
}
