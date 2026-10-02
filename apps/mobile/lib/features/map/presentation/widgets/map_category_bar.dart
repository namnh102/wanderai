import 'package:flutter/material.dart';
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
    final theme = Theme.of(context);

    return SizedBox(
      height: 40,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        itemCount: mapCategories.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (context, index) {
          final cat = mapCategories[index];
          final isSelected = (selectedCategory == null && cat.key == 'all') ||
              selectedCategory == cat.key;

          return FilterChip(
            selected: isSelected,
            label: Text(cat.label),
            avatar: Icon(
              _iconForKey(cat.key),
              size: 16,
              color: isSelected
                  ? theme.colorScheme.onPrimary
                  : theme.colorScheme.onSurfaceVariant,
            ),
            onSelected: (_) => onCategorySelected(cat.key),
            backgroundColor: theme.colorScheme.surface,
            selectedColor: theme.colorScheme.primary,
            labelStyle: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: isSelected
                  ? theme.colorScheme.onPrimary
                  : theme.colorScheme.onSurfaceVariant,
            ),
            side: BorderSide(
              color: isSelected
                  ? theme.colorScheme.primary
                  : theme.colorScheme.outline.withValues(alpha: 0.3),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 4),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
            elevation: 2,
            pressElevation: 4,
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
      case 'temple': return Icons.temple_buddhist;
      case 'beach': return Icons.beach_access;
      case 'museum': return Icons.museum;
      case 'park': return Icons.park;
      case 'market': return Icons.store;
      case 'cafe': return Icons.local_cafe;
      default: return Icons.place;
    }
  }
}
