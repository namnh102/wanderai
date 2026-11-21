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
      height: 42,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        children: [
          for (final d in supportedDestinations)
            Padding(
              padding: const EdgeInsets.only(right: 8),
              child: ChoiceChip(
                key: Key('map_destination_chip_${d.slug}'),
                showCheckmark: false,
                label: Text(d.label),
                selected: selectedSlug == d.slug,
                selectedColor: AppColors.primaryContainer,
                backgroundColor: AppColors.surface,
                labelStyle: TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                  color: selectedSlug == d.slug
                      ? AppColors.primaryDeep
                      : AppColors.textPrimary,
                ),
                side: BorderSide(
                  color: selectedSlug == d.slug
                      ? AppColors.primary
                      : AppColors.softBorder,
                ),
                shape: const StadiumBorder(),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                onSelected: (_) => onSelected(d.slug),
              ),
            ),
        ],
      ),
    );
  }
}
