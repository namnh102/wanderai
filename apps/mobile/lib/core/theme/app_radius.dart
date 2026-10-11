import 'package:flutter/material.dart';

/// GoMate Corner Radius System.
/// Source of truth: docs/design/gomate-design-system-ux-spec-v1.md Section 3.5
class AppRadius {
  AppRadius._();

  static const double sm = 8.0; // Small controls, input fields, badges
  static const double md = 12.0; // Standard buttons, chips
  static const double card = 16.0; // Standard content cards
  static const double hero = 20.0; // Large hero cards, banners
  static const double sheet = 24.0; // Bottom sheet top corners
  static const double pill = 999.0; // Circular buttons, tag pills

  // Border Radii helper instances
  static const BorderRadius smRadius = BorderRadius.all(Radius.circular(sm));
  static const BorderRadius mdRadius = BorderRadius.all(Radius.circular(md));
  static const BorderRadius cardRadius = BorderRadius.all(Radius.circular(card));
  static const BorderRadius heroRadius = BorderRadius.all(Radius.circular(hero));
  static const BorderRadius sheetRadius = BorderRadius.vertical(top: Radius.circular(sheet));
  static const BorderRadius pillRadius = BorderRadius.all(Radius.circular(pill));
}
