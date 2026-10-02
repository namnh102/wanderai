import 'package:flutter/material.dart';
import '../../data/place_model.dart';

/// Bottom sheet showing place preview when a marker is tapped.
class PlacePreviewSheet extends StatelessWidget {
  final PlaceModel place;
  final VoidCallback onClose;

  const PlacePreviewSheet({
    super.key,
    required this.place,
    required this.onClose,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bottomPadding = MediaQuery.of(context).padding.bottom;

    return Container(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 12,
        bottom: bottomPadding + 12,
      ),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.15),
            blurRadius: 16,
            offset: const Offset(0, -4),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Handle bar
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: theme.colorScheme.outline.withValues(alpha: 0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 12),

          // Header row
          Row(
            children: [
              // Category icon
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _categoryColor(place.categoryName).withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(
                  _categoryIcon(place.categoryName),
                  color: _categoryColor(place.categoryName),
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),

              // Name and category
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      place.name,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    if (place.categoryName != null)
                      Text(
                        _categoryLabel(place.categoryName!),
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: _categoryColor(place.categoryName),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                  ],
                ),
              ),

              // Close button
              IconButton(
                onPressed: onClose,
                icon: const Icon(Icons.close, size: 20),
                style: IconButton.styleFrom(
                  padding: const EdgeInsets.all(4),
                  minimumSize: const Size(32, 32),
                ),
              ),
            ],
          ),

          const SizedBox(height: 12),

          // Info chips row
          Wrap(
            spacing: 8,
            runSpacing: 6,
            children: [
              // Rating
              if (place.rating > 0)
                _InfoChip(
                  icon: Icons.star,
                  label: place.rating.toStringAsFixed(1),
                  color: Colors.amber,
                ),

              // Review count
              if (place.reviewCount > 0)
                _InfoChip(
                  icon: Icons.rate_review_outlined,
                  label: '${place.reviewCount} đánh giá',
                  color: theme.colorScheme.onSurfaceVariant,
                ),

              // Distance
              if (place.distanceKm != null)
                _InfoChip(
                  icon: Icons.near_me,
                  label: place.distanceKm! < 1
                      ? '${(place.distanceKm! * 1000).toInt()}m'
                      : '${place.distanceKm!.toStringAsFixed(1)} km',
                  color: theme.colorScheme.primary,
                ),

              // Verified badge
              if (place.isVerified)
                _InfoChip(
                  icon: Icons.verified,
                  label: 'Đã xác minh',
                  color: theme.colorScheme.primary,
                ),

              // Destination
              if (place.destinationName != null)
                _InfoChip(
                  icon: Icons.location_city,
                  label: place.destinationName!,
                  color: theme.colorScheme.onSurfaceVariant,
                ),
            ],
          ),

          // Address
          if (place.address != null && place.address!.isNotEmpty) ...[
            const SizedBox(height: 10),
            Row(
              children: [
                Icon(Icons.location_on_outlined,
                    size: 16, color: theme.colorScheme.onSurfaceVariant),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    place.address!,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ],

          const SizedBox(height: 12),

          // Coordinates (small)
          if (place.hasCoordinates)
            Text(
              '${place.latitude!.toStringAsFixed(5)}, ${place.longitude!.toStringAsFixed(5)}',
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.outline,
                fontFamily: 'monospace',
              ),
            ),
        ],
      ),
    );
  }

  Color _categoryColor(String? category) {
    switch (category?.toLowerCase()) {
      case 'attraction': return const Color(0xFF9C27B0);
      case 'restaurant': return const Color(0xFFFF5722);
      case 'hotel': return const Color(0xFF2196F3);
      case 'temple': case 'pagoda': return const Color(0xFFFF9800);
      case 'beach': return const Color(0xFF00BCD4);
      case 'museum': return const Color(0xFF607D8B);
      case 'park': return const Color(0xFF8BC34A);
      case 'market': return const Color(0xFF4CAF50);
      case 'cafe': return const Color(0xFF795548);
      default: return const Color(0xFF00685F);
    }
  }

  IconData _categoryIcon(String? category) {
    switch (category?.toLowerCase()) {
      case 'attraction': return Icons.attractions;
      case 'restaurant': return Icons.restaurant;
      case 'hotel': return Icons.hotel;
      case 'temple': case 'pagoda': return Icons.temple_buddhist;
      case 'beach': return Icons.beach_access;
      case 'museum': return Icons.museum;
      case 'park': return Icons.park;
      case 'market': return Icons.store;
      case 'cafe': return Icons.local_cafe;
      default: return Icons.place;
    }
  }

  String _categoryLabel(String category) {
    switch (category.toLowerCase()) {
      case 'attraction': return 'Tham quan';
      case 'restaurant': return 'Nhà hàng';
      case 'hotel': return 'Khách sạn';
      case 'temple': case 'pagoda': return 'Đền/Chùa';
      case 'beach': return 'Biển';
      case 'museum': return 'Bảo tàng';
      case 'park': return 'Công viên';
      case 'market': return 'Chợ';
      case 'cafe': return 'Cà phê';
      default: return category;
    }
  }
}

class _InfoChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final Color color;

  const _InfoChip({
    required this.icon,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: color,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
