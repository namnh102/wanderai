import 'package:flutter/material.dart';

/// Wraps mobile screens on tablet / desktop web viewports to prevent
/// horizontal stretching and maintain optimal mobile reading width.
/// Source of truth: docs/design/gomate-design-system-ux-spec-v1.md Section 10
class ResponsiveWrapper extends StatelessWidget {
  final Widget child;
  final double maxWidth;
  final EdgeInsetsGeometry? padding;
  final bool fillHeight;

  const ResponsiveWrapper({
    super.key,
    required this.child,
    this.maxWidth = 640.0,
    this.padding,
    this.fillHeight = true,
  });

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      widthFactor: 1.0,
      heightFactor: fillHeight ? null : 1.0,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: padding != null ? Padding(padding: padding!, child: child) : child,
      ),
    );
  }
}
