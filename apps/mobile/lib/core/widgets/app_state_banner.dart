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
  final int? maxLines;
  final bool compact;

  const AppStateBanner({
    super.key,
    required this.message,
    this.actionLabel,
    this.onAction,
    this.tone = AppStateBannerTone.info,
    this.icon,
    this.maxLines,
    this.compact = false,
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

    final hasAction = actionLabel != null && onAction != null;
    final textScale = MediaQuery.textScalerOf(context).scale(14.0) / 14.0;
    final messageStyle = AppTypography.bodyS.copyWith(
      color: fg,
      fontWeight: FontWeight.w500,
      fontSize: compact ? 12.5 : null,
      height: compact ? 1.25 : null,
    );
    final buttonStyle = TextButton.styleFrom(
      foregroundColor: fg,
      tapTargetSize: compact ? MaterialTapTargetSize.shrinkWrap : null,
      minimumSize: compact ? const Size(44, 28) : const Size(44, 36),
      padding: EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: compact ? 2 : 0,
      ),
      textStyle: AppTypography.label.copyWith(
        color: fg,
        fontWeight: FontWeight.w700,
      ),
    );

    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 10 : AppSpacing.mdSmall,
        vertical: compact ? 6 : AppSpacing.sm,
      ),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: AppRadius.mdRadius,
        border: Border.all(color: border, width: 1),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final stackAction = hasAction &&
              (compact || constraints.maxWidth < 300 || textScale > 1.25);

          if (stackAction) {
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(top: 1),
                      child: Icon(icon ?? defaultIcon, size: 18, color: fg),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Text(
                        message,
                        maxLines: maxLines,
                        overflow:
                            maxLines != null ? TextOverflow.ellipsis : null,
                        style: messageStyle,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: onAction,
                    style: buttonStyle,
                    child: Text(
                      actionLabel!,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
              ],
            );
          }

          return Row(
            children: [
              Icon(icon ?? defaultIcon, size: 18, color: fg),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  message,
                  maxLines: maxLines,
                  overflow: maxLines != null ? TextOverflow.ellipsis : null,
                  style: messageStyle,
                ),
              ),
              if (hasAction)
                TextButton(
                  onPressed: onAction,
                  style: buttonStyle,
                  child: Text(
                    actionLabel!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
