import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_spacing.dart';
import '../theme/app_typography.dart';

enum AppButtonVariant { primary, secondary, ai, tonal }

/// Unified GoMate Button component.
/// Source of truth: docs/design/gomate-design-system-ux-spec-v1.md Section 4.2 - 4.4
class AppButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool isLoading;
  final bool isFullWidth;
  final AppButtonVariant variant;

  const AppButton({
    super.key,
    required this.text,
    this.onPressed,
    this.icon,
    this.isLoading = false,
    this.isFullWidth = true,
    this.variant = AppButtonVariant.primary,
  });

  @override
  Widget build(BuildContext context) {
    final bool enabled = onPressed != null && !isLoading;

    Color bgColor;
    Color fgColor;
    BorderSide borderSide = BorderSide.none;

    switch (variant) {
      case AppButtonVariant.primary:
        bgColor = AppColors.primary;
        fgColor = AppColors.onPrimary;
        break;
      case AppButtonVariant.secondary:
        bgColor = Colors.transparent;
        fgColor = AppColors.primary;
        borderSide = const BorderSide(color: AppColors.primary, width: 1.5);
        break;
      case AppButtonVariant.ai:
        bgColor = AppColors.primary;
        fgColor = AppColors.onPrimary;
        break;
      case AppButtonVariant.tonal:
        bgColor = AppColors.primaryContainer;
        fgColor = AppColors.onPrimaryContainer;
        break;
    }

    Widget content;
    if (isLoading) {
      content = SizedBox(
        width: 20,
        height: 20,
        child: CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation<Color>(fgColor),
        ),
      );
    } else {
      final IconData? effectiveIcon =
          variant == AppButtonVariant.ai ? Icons.auto_awesome : icon;

      if (effectiveIcon != null) {
        content = Row(
          mainAxisSize: MainAxisSize.min,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(effectiveIcon, size: 18, color: fgColor),
            const SizedBox(width: AppSpacing.sm),
            Text(
              text,
              style: AppTypography.button.copyWith(color: fgColor),
            ),
          ],
        );
      } else {
        content = Text(
          text,
          style: AppTypography.button.copyWith(color: fgColor),
        );
      }
    }

    final buttonWidget = Material(
      color: enabled ? bgColor : AppColors.disabled.withValues(alpha: 0.3),
      shape: RoundedRectangleBorder(
        borderRadius: AppRadius.mdRadius,
        side: enabled ? borderSide : BorderSide.none,
      ),
      child: InkWell(
        onTap: enabled ? onPressed : null,
        borderRadius: AppRadius.mdRadius,
        child: Container(
          height: 48,
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
          alignment: Alignment.center,
          child: content,
        ),
      ),
    );

    if (isFullWidth) {
      return SizedBox(width: double.infinity, child: buttonWidget);
    }
    return buttonWidget;
  }
}
