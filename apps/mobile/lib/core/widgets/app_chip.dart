import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

/// GoMate AppChip for category filtering, tags, and selection.
class AppChip extends StatelessWidget {
  final String label;
  final IconData? icon;
  final bool isSelected;
  final VoidCallback? onTap;
  final Color? activeColor;

  const AppChip({
    super.key,
    required this.label,
    this.icon,
    this.isSelected = false,
    this.onTap,
    this.activeColor,
  });

  @override
  Widget build(BuildContext context) {
    final effectiveColor = activeColor ?? AppColors.primary;

    final bgColor = isSelected
        ? effectiveColor.withValues(alpha: 0.12)
        : AppColors.surface;

    final textColor = isSelected ? effectiveColor : AppColors.textSecondary;
    final borderColor = isSelected
        ? effectiveColor
        : AppColors.border;

    return Material(
      color: bgColor,
      shape: RoundedRectangleBorder(
        borderRadius: AppRadius.pillRadius,
        side: BorderSide(color: borderColor, width: isSelected ? 1.5 : 1.0),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: AppRadius.pillRadius,
        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.mdSmall,
            vertical: AppSpacing.sm,
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (icon != null) ...[
                Icon(icon, size: 16, color: textColor),
                const SizedBox(width: AppSpacing.xs),
              ],
              Text(
                label,
                style: AppTypography.label.copyWith(
                  color: textColor,
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
