import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../data/destination_model.dart';

/// Compact destination chips (Hà Nội / Đà Nẵng / Hạ Long).
///
/// [selectedSlug] is null in SEARCH / NEARBY modes: no chip is highlighted.
class MapDestinationSelector extends StatelessWidget {
  final String? selectedSlug;
  final ValueChanged<String> onSelected;

  const MapDestinationSelector({
    super.key,
    required this.selectedSlug,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 36,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        children: [
          for (final d in supportedDestinations)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                key: Key('map_destination_chip_${d.slug}'),
                label: Text(d.label),
                selected: selectedSlug == d.slug,
                selectedColor: AppColors.primaryContainer,
                backgroundColor: AppColors.surface,
                visualDensity: VisualDensity.compact,
                onSelected: (_) => onSelected(d.slug),
              ),
            ),
        ],
      ),
    );
  }
}
