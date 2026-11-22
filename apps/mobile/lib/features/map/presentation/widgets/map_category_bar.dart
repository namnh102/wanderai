import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';
import '../../providers/map_provider.dart';

/// Horizontal scrolling category filter bar for the map.
class MapCategoryBar extends StatelessWidget {
  final String? selectedCategory;
  final ValueChanged<String?> onCategorySelected;

  const MapCategoryBar({
    super.key,
    required this.selectedCategory,
    required this.onCategorySelected,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 44,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        itemCount: mapCategories.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, index) {
          final cat = mapCategories[index];
          final isSelected = (selectedCategory == null && cat.key == 'all') ||
              selectedCategory == cat.key;

          return FilterChip(
            selected: isSelected,
            showCheckmark: false,
            label: Text(cat.label),
            avatar: Icon(
              _iconForKey(cat.key),
              size: 16,
              color: isSelected ? AppColors.onPrimary : AppColors.textSecondary,
            ),
            onSelected: (_) => onCategorySelected(cat.key),
            backgroundColor: AppColors.surface,
            selectedColor: AppColors.primary,
            labelStyle: TextStyle(
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
              color: isSelected ? AppColors.onPrimary : AppColors.textPrimary,
            ),
            side: BorderSide(
              color: isSelected ? AppColors.primary : AppColors.softBorder,
            ),
            shape: const StadiumBorder(),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            labelPadding: const EdgeInsets.only(left: 4, right: 2),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            elevation: isSelected ? 2 : 1,
            shadowColor: AppColors.primaryDeep.withValues(alpha: 0.14),
            pressElevation: 3,
          );
        },
      ),
    );
  }

  IconData _iconForKey(String key) {
    switch (key) {
      case 'all': return Icons.category;
      case 'attraction': return Icons.attractions;
      case 'restaurant': return Icons.restaurant;
      case 'hotel': return Icons.hotel;
      case 'culture': return Icons.museum;
      case 'beach': return Icons.beach_access;
      case 'nature': return Icons.park;
      case 'entertainment': return Icons.celebration;
      case 'cafe': return Icons.local_cafe;
      default: return Icons.place;
    }
  }
}
