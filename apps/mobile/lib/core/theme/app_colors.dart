import 'package:flutter/material.dart';

/// Centralized GoMate Design System Colors.
/// Source of truth: docs/design/gomate-design-system-ux-spec-v1.md
class AppColors {
  AppColors._();

  // ─── Brand Colors ───
  static const Color primary = Color(0xFF0F766E); // Teal-700
  static const Color primaryContainer = Color(0xFFCCFBF1); // Teal-100
  static const Color onPrimary = Color(0xFFFFFFFF);
  static const Color onPrimaryContainer = Color(0xFF115E59); // Teal-800

  // ─── Semantic Colors ───
  static const Color success = Color(0xFF15803D); // Green-700
  static const Color successContainer = Color(0xFFDCFCE7); // Green-100
  static const Color onSuccess = Color(0xFFFFFFFF);

  static const Color warning = Color(0xFFB45309); // Amber-700
  static const Color warningContainer = Color(0xFFFEF3C7); // Amber-100
  static const Color onWarning = Color(0xFFFFFFFF);

  static const Color error = Color(0xFFB91C1C); // Red-700
  static const Color errorContainer = Color(0xFFFEE2E2); // Red-100
  static const Color onError = Color(0xFFFFFFFF);

  static const Color info = Color(0xFF2563EB); // Blue-600
  static const Color infoContainer = Color(0xFFDBEAFE); // Blue-100
  static const Color onInfo = Color(0xFFFFFFFF);

  // ─── Neutral Colors ───
  static const Color background = Color(0xFFF8FAFC); // Slate-50
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceContainer = Color(0xFFF1F5F9); // Slate-100
  static const Color surfaceContainerHigh = Color(0xFFE2E8F0); // Slate-200
  static const Color surfaceContainerLow = Color(0xFFF8FAFC);

  static const Color textPrimary = Color(0xFF0F172A); // Slate-900
  static const Color textSecondary = Color(0xFF475569); // Slate-600
  static const Color textTertiary = Color(0xFF94A3B8); // Slate-400

  static const Color border = Color(0xFFE2E8F0); // Slate-200
  static const Color divider = Color(0xFFE2E8F0);
  static const Color disabled = Color(0xFF94A3B8);

  // ─── Category Semantic Palette ───
  static const Color catAttraction = Color(0xFF9333EA); // Purple-600
  static const Color catCulture = Color(0xFF4F46E5); // Indigo-600
  static const Color catNature = Color(0xFF16A34A); // Green-600
  static const Color catBeach = Color(0xFF0284C7); // Sky-600
  static const Color catCafe = Color(0xFF78350F); // Amber-900
  static const Color catRestaurant = Color(0xFFEA580C); // Orange-600
  static const Color catHotel = Color(0xFF0D9488); // Teal-600
  static const Color catEntertainment = Color(0xFFDB2777); // Pink-600

  /// Resolve color for a category slug or name.
  static Color forCategory(String? category) {
    switch (category?.toLowerCase()) {
      case 'attraction':
      case 'tham quan':
        return catAttraction;
      case 'culture':
      case 'văn hóa':
      case 'museum':
      case 'bảo tàng':
      case 'temple':
      case 'pagoda':
        return catCulture;
      case 'nature':
      case 'thiên nhiên':
      case 'park':
      case 'công viên':
        return catNature;
      case 'beach':
      case 'biển':
        return catBeach;
      case 'cafe':
      case 'cà phê':
        return catCafe;
      case 'restaurant':
      case 'nhà hàng':
      case 'ẩm thực':
        return catRestaurant;
      case 'hotel':
      case 'lưu trú':
      case 'khách sạn':
        return catHotel;
      case 'entertainment':
      case 'giải trí':
        return catEntertainment;
      default:
        return primary;
    }
  }
}
