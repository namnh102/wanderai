import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// GoMate Badge for verification status and semantic metadata.
class AppBadge extends StatelessWidget {
  final String label;
  final IconData? icon;
  final Color color;
  final Color? backgroundColor;

  const AppBadge({
    super.key,
    required this.label,
    this.icon,
    this.color = AppColors.primary,
    this.backgroundColor,
  });

  /// Factory for the official GoMate "✓ Đã xác minh" badge.
  factory AppBadge.verified({Key? key}) {
    return AppBadge(
      key: key,
      label: 'Đã xác minh',
      icon: Icons.verified,
      color: AppColors.primary,
      backgroundColor: AppColors.primaryContainer,
    );
  }

  @override
  Widget build(BuildContext context) {
    final bg = backgroundColor ?? color.withValues(alpha: 0.12);

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: AppRadius.smRadius,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
          ],
          Text(
            label,
            style: AppTypography.label.copyWith(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
