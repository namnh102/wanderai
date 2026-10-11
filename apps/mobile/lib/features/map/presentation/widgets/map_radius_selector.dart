import 'package:flutter/material.dart';
import '../../providers/map_provider.dart';

/// Floating radius selector button with popup menu.
class MapRadiusSelector extends StatelessWidget {
  final double currentRadius;
  final ValueChanged<double> onRadiusChanged;

  const MapRadiusSelector({
    super.key,
    required this.currentRadius,
    required this.onRadiusChanged,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return PopupMenuButton<double>(
      onSelected: onRadiusChanged,
      tooltip: 'Bán kính tìm kiếm',
      offset: const Offset(-120, 0),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      itemBuilder: (context) => radiusOptions.map((r) {
        final isSelected = r == currentRadius;
        return PopupMenuItem<double>(
          value: r,
          child: Row(
            children: [
              Icon(
                isSelected ? Icons.radio_button_checked : Icons.radio_button_off,
                size: 18,
                color: isSelected ? theme.colorScheme.primary : theme.colorScheme.outline,
              ),
              const SizedBox(width: 8),
              Text(
                r < 1 ? '${(r * 1000).toInt()}m' : '${r.toInt()} km',
                style: TextStyle(
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w400,
                  color: isSelected ? theme.colorScheme.primary : null,
                ),
              ),
            ],
          ),
        );
      }).toList(),
      child: Material(
        elevation: 4,
        shape: const CircleBorder(),
        color: theme.colorScheme.surface,
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.radar, size: 22, color: theme.colorScheme.primary),
              Text(
                '${currentRadius.toInt()}km',
                style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w700,
                  color: theme.colorScheme.primary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
