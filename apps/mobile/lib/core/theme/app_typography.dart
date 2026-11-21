import 'package:flutter/material.dart';
import 'app_colors.dart';

/// GoMate Typography System.
/// Source of truth: docs/design/gomate-design-system-ux-spec-v1.md Section 3.3
class AppTypography {
  AppTypography._();

  static const List<String> _fontFallback = [
    'Be Vietnam Pro',
    'Plus Jakarta Sans',
    'Roboto',
    'Noto Sans',
    'sans-serif',
  ];

  static const TextStyle display = TextStyle(
    fontSize: 30,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
    letterSpacing: -0.5,
    height: 1.25,
    fontFamilyFallback: _fontFallback,
  );

  static const TextStyle h1 = TextStyle(
    fontSize: 24,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
    letterSpacing: -0.3,
    height: 1.3,
    fontFamilyFallback: _fontFallback,
  );

  static const TextStyle h2 = TextStyle(
    fontSize: 20,
    fontWeight: FontWeight.w700,
    color: AppColors.textPrimary,
    letterSpacing: -0.2,
    height: 1.35,
    fontFamilyFallback: _fontFallback,
  );

  static const TextStyle h3 = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
    height: 1.4,
    fontFamilyFallback: _fontFallback,
  );

  static const TextStyle bodyL = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w400,
    color: AppColors.textPrimary,
    height: 1.5,
    fontFamilyFallback: _fontFallback,
  );

  static const TextStyle bodyM = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
    height: 1.5,
    fontFamilyFallback: _fontFallback,
  );

  static const TextStyle bodyS = TextStyle(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    color: AppColors.textTertiary,
    height: 1.4,
    fontFamilyFallback: _fontFallback,
  );

  static const TextStyle label = TextStyle(
    fontSize: 12,
    fontWeight: FontWeight.w600,
    color: AppColors.textPrimary,
    letterSpacing: 0.1,
    fontFamilyFallback: _fontFallback,
  );

  static const TextStyle eyebrow = TextStyle(
    fontSize: 11,
    fontWeight: FontWeight.w700,
    color: AppColors.primary,
    letterSpacing: 0.6,
    fontFamilyFallback: _fontFallback,
  );

  static const TextStyle caption = TextStyle(
    fontSize: 11.5,
    fontWeight: FontWeight.w500,
    color: AppColors.textSecondary,
    height: 1.35,
    fontFamilyFallback: _fontFallback,
  );

  static const TextStyle button = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w600,
    color: AppColors.onPrimary,
    letterSpacing: 0.2,
    fontFamilyFallback: _fontFallback,
  );
}
