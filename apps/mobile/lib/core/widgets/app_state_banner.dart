import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

enum AppStateBannerTone { info, warning, error }

/// Non-blocking inline state banner for partial data, offline, or warning states.
class AppStateBanner extends StatelessWidget {
  final String message;
  final String? actionLabel;
  final VoidCallback? onAction;
  final AppStateBannerTone tone;
  final IconData? icon;

  const AppStateBanner({
    super.key,
    required this.message,
    this.actionLabel,
    this.onAction,
    this.tone = AppStateBannerTone.info,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final (Color bg, Color fg, Color border, IconData defaultIcon) = switch (tone) {
      AppStateBannerTone.info => (
          AppColors.primaryContainer.withValues(alpha: 0.45),
          AppColors.primaryDeep,
          AppColors.primary.withValues(alpha: 0.25),
          Icons.info_outline_rounded,
        ),
      AppStateBannerTone.warning => (
          AppColors.warningContainer.withValues(alpha: 0.7),
          AppColors.warning,
          AppColors.warning.withValues(alpha: 0.28),
          Icons.wifi_off_rounded,
        ),
      AppStateBannerTone.error => (
          AppColors.errorContainer,
          AppColors.error,
          AppColors.error.withValues(alpha: 0.25),
          Icons.error_outline_rounded,
        ),
    };

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.mdSmall,
        vertical: AppSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: AppRadius.mdRadius,
        border: Border.all(color: border, width: 1),
      ),
      child: Row(
        children: [
          Icon(icon ?? defaultIcon, size: 18, color: fg),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: AppTypography.bodyS.copyWith(
                color: fg,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          if (actionLabel != null && onAction != null)
            TextButton(
              onPressed: onAction,
              style: TextButton.styleFrom(
                foregroundColor: fg,
                minimumSize: const Size(44, 36),
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                textStyle: AppTypography.label.copyWith(
                  color: fg,
                  fontWeight: FontWeight.w700,
                ),
              ),
              child: Text(actionLabel!),
            ),
        ],
      ),
    );
  }
}
