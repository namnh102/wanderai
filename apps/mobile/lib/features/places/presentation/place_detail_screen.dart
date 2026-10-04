import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_radius.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_badge.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_empty_state.dart';
import '../../../core/widgets/app_error_state.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/rating_view.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../../map/data/place_model.dart';
import '../providers/place_detail_provider.dart';
import 'widgets/place_mini_map.dart';

/// Vietnamese label for a stored category key.
String placeCategoryLabel(String category) {
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
    case 'entertainment': return 'Giải trí';
    case 'culture': return 'Văn hóa';
    case 'nature': return 'Thiên nhiên';
    default: return category;
  }
}

IconData placeCategoryIcon(String? category) {
  switch (category?.toLowerCase()) {
    case 'attraction': return Icons.attractions;
    case 'restaurant': return Icons.restaurant;
    case 'hotel': return Icons.hotel;
    case 'temple': case 'pagoda': return Icons.temple_buddhist;
    case 'beach': return Icons.beach_access;
    case 'museum': case 'culture': return Icons.museum;
    case 'park': case 'nature': return Icons.park;
    case 'market': return Icons.store;
    case 'cafe': return Icons.local_cafe;
    default: return Icons.place;
  }
}

/// Coordinates-only "Chỉ đường" target. No routing provider is invented:
/// a neutral `geo:` URI is handed to the OS; where unsupported (e.g. web),
/// the OSM location of the same coordinates is opened.
Uri directionsGeoUri(PlaceModel p) => Uri.parse(
    'geo:${p.latitude},${p.longitude}?q=${p.latitude},${p.longitude}');

Uri directionsFallbackUri(PlaceModel p) => Uri.parse(
    'https://www.openstreetmap.org/?mlat=${p.latitude}&mlon=${p.longitude}'
    '#map=17/${p.latitude}/${p.longitude}');

Future<void> _openExternal(Uri uri) async {
  try {
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  } catch (_) {
    // Link could not be opened — ignore silently.
  }
}

Future<void> _openDirections(PlaceModel p) async {
  final geo = directionsGeoUri(p);
  try {
    if (await canLaunchUrl(geo)) {
      await launchUrl(geo);
      return;
    }
  } catch (_) {}
  await _openExternal(directionsFallbackUri(p));
}

/// Place Detail screen — route `/places/:id`.
class PlaceDetailScreen extends ConsumerWidget {
  final String placeId;
  const PlaceDetailScreen({super.key, required this.placeId});

  void _back(BuildContext context) {
    if (context.canPop()) {
      context.pop();
    } else {
      context.go('/map');
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(placeDetailProvider(placeId));

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        foregroundColor: AppColors.textPrimary,
        elevation: 0,
        leading: IconButton(
          key: const Key('place_detail_back'),
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Quay lại',
          onPressed: () => _back(context),
        ),
        title: const Text('Chi tiết địa điểm', style: AppTypography.h3),
      ),
      body: detail.when(
        loading: () => const AppLoading(message: 'Đang tải thông tin địa điểm...'),
        error: (e, _) {
          final status = e is DioException ? e.response?.statusCode : null;
          if (status == 404 || status == 400) {
            return AppEmptyState(
              icon: Icons.location_off_outlined,
              title: 'Không tìm thấy địa điểm',
              description: 'Địa điểm này không tồn tại hoặc đã bị gỡ.',
              actionLabel: 'Về bản đồ',
              onAction: () => context.go('/map'),
            );
          }
          return AppErrorState(
            message: 'Không thể tải thông tin địa điểm. Vui lòng thử lại.',
            onRetry: () => ref.invalidate(placeDetailProvider(placeId)),
          );
        },
        data: (place) => PlaceDetailView(
          place: place,
          onOpenUrl: (url) => _openExternal(Uri.parse(url)),
          onDirections: () => _openDirections(place),
        ),
      ),
    );
  }
}

/// Pure presentation of a place's factual data. Unavailable fields render an
/// honest "not available" state or are omitted — never invented.
class PlaceDetailView extends StatelessWidget {
  final PlaceModel place;
  final void Function(String url) onOpenUrl;
  final VoidCallback onDirections;

  const PlaceDetailView({
    super.key,
    required this.place,
    required this.onOpenUrl,
    required this.onDirections,
  });

  @override
  Widget build(BuildContext context) {
    final catColor = AppColors.forCategory(place.categoryName);
    final hasHours = place.openingHours != null;
    final hasContact = place.website != null || place.phone != null;

    return ResponsiveWrapper(
      maxWidth: 640.0,
      child: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.screenHorizontal),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── Hero header ──
                  Container(
                    key: const Key('place_detail_hero'),
                    width: double.infinity,
                    padding: const EdgeInsets.all(AppSpacing.md),
                    decoration: BoxDecoration(
                      color: catColor.withValues(alpha: 0.10),
                      borderRadius: AppRadius.heroRadius,
                      border: Border.all(color: catColor.withValues(alpha: 0.25)),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(AppSpacing.sm),
                          decoration: BoxDecoration(
                            color: catColor.withValues(alpha: 0.18),
                            borderRadius: AppRadius.smRadius,
                          ),
                          child: Icon(placeCategoryIcon(place.categoryName),
                              color: catColor, size: 28),
                        ),
                        const SizedBox(height: AppSpacing.mdSmall),
                        Text(place.name, style: AppTypography.h2),
                        if (place.nameEn != null &&
                            place.nameEn!.isNotEmpty &&
                            place.nameEn != place.name) ...[
                          const SizedBox(height: AppSpacing.xs),
                          Text(place.nameEn!,
                              style: AppTypography.bodyM
                                  .copyWith(color: AppColors.textSecondary)),
                        ],
                        const SizedBox(height: AppSpacing.mdSmall),
                        Wrap(
                          spacing: AppSpacing.sm,
                          runSpacing: AppSpacing.xs,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            if (place.categoryName != null)
                              Text(
                                placeCategoryLabel(place.categoryName!),
                                key: const Key('place_detail_category'),
                                style: AppTypography.label.copyWith(
                                    color: catColor,
                                    fontWeight: FontWeight.w700),
                              ),
                            // Badge only for genuine provenance.
                            if (place.isVerified) AppBadge.verified(),
                            if (place.destinationName != null)
                              Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const Icon(Icons.location_city,
                                      size: 14, color: AppColors.textSecondary),
                                  const SizedBox(width: AppSpacing.xs),
                                  Text(place.destinationName!,
                                      style: AppTypography.bodyS),
                                ],
                              ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),

                  // ── Rating ──
                  _Section(
                    icon: Icons.star_border,
                    title: 'Đánh giá',
                    child: RatingView(
                      rating: place.rating,
                      reviewCount: place.reviewCount,
                      iconSize: 18,
                    ),
                  ),

                  // ── Address ──
                  _Section(
                    icon: Icons.location_on_outlined,
                    title: 'Địa chỉ',
                    child: place.hasAddress
                        ? Text(place.addressDisplay, style: AppTypography.bodyM)
                        : const _Unavailable(PlaceModel.addressUnavailableText),
                  ),

                  // ── Opening hours ──
                  _Section(
                    icon: Icons.schedule,
                    title: 'Giờ mở cửa',
                    child: hasHours
                        ? Text(place.openingHours!, style: AppTypography.bodyM)
                        : const _Unavailable('Chưa có thông tin giờ mở cửa.'),
                  ),

                  // ── Contact (only what exists) ──
                  if (hasContact)
                    _Section(
                      icon: Icons.contact_phone_outlined,
                      title: 'Liên hệ',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (place.website != null)
                            _LinkRow(
                              key: const Key('place_detail_website'),
                              icon: Icons.language,
                              text: place.website!,
                              onTap: () => onOpenUrl(place.website!),
                            ),
                          if (place.phone != null)
                            _LinkRow(
                              key: const Key('place_detail_phone'),
                              icon: Icons.phone_outlined,
                              text: place.phone!,
                              onTap: () => onOpenUrl(
                                  'tel:${place.phone!.replaceAll(' ', '')}'),
                            ),
                        ],
                      ),
                    ),

                  // ── Description (only if stored for a verified place) ──
                  if (place.description != null &&
                      place.description!.trim().isNotEmpty)
                    _Section(
                      icon: Icons.notes,
                      title: 'Mô tả',
                      child: Text(place.description!,
                          style: AppTypography.bodyM),
                    ),

                  // ── Coordinates / mini map ──
                  if (place.hasCoordinates)
                    _Section(
                      icon: Icons.map_outlined,
                      title: 'Vị trí',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${place.latitude!.toStringAsFixed(5)}, '
                            '${place.longitude!.toStringAsFixed(5)}',
                            key: const Key('place_detail_coordinates'),
                            style: AppTypography.bodyS.copyWith(
                                color: AppColors.textSecondary,
                                fontFamily: 'monospace'),
                          ),
                          const SizedBox(height: AppSpacing.sm),
                          PlaceMiniMap(place: place),
                        ],
                      ),
                    ),

                  // ── OSM provenance ──
                  _Section(
                    icon: Icons.verified_outlined,
                    title: 'Nguồn dữ liệu',
                    child: place.source != null
                        ? Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Nguồn: ${place.source!.name}',
                                  key: const Key('place_detail_source_label'),
                                  style: AppTypography.bodyM.copyWith(
                                      fontWeight: FontWeight.w600)),
                              _LinkRow(
                                key: const Key('place_detail_source_url'),
                                icon: Icons.open_in_new,
                                text: place.source!.canonicalUrl,
                                onTap: () =>
                                    onOpenUrl(place.source!.canonicalUrl),
                              ),
                              if (place.source!.license != null ||
                                  place.source!.attribution != null)
                                Text(
                                  [place.source!.attribution,
                                          if (place.source!.license != null)
                                            'Giấy phép ${place.source!.license}']
                                      .whereType<String>()
                                      .join(' · '),
                                  style: AppTypography.bodyS.copyWith(
                                      color: AppColors.textTertiary),
                                ),
                            ],
                          )
                        : const _Unavailable(
                            'Địa điểm này chưa được xác minh nguồn dữ liệu.'),
                  ),
                  const SizedBox(height: AppSpacing.md),
                ],
              ),
            ),
          ),

          // ── Primary CTA ──
          if (place.hasCoordinates)
            Container(
              width: double.infinity,
              padding: EdgeInsets.fromLTRB(
                AppSpacing.md,
                AppSpacing.sm,
                AppSpacing.md,
                AppSpacing.sm + MediaQuery.of(context).padding.bottom,
              ),
              decoration: const BoxDecoration(
                color: AppColors.surface,
                border: Border(top: BorderSide(color: AppColors.border)),
              ),
              child: AppButton(
                key: const Key('place_detail_directions'),
                text: 'Chỉ đường',
                icon: Icons.directions,
                onPressed: onDirections,
              ),
            ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final IconData icon;
  final String title;
  final Widget child;
  const _Section({required this.icon, required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.mdSmall),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: AppRadius.cardRadius,
          border: Border.all(color: AppColors.border),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 18, color: AppColors.primary),
                const SizedBox(width: AppSpacing.sm),
                Text(title, style: AppTypography.h3.copyWith(fontSize: 15)),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            child,
          ],
        ),
      ),
    );
  }
}

class _Unavailable extends StatelessWidget {
  final String text;
  const _Unavailable(this.text);

  @override
  Widget build(BuildContext context) => Text(
        text,
        style: AppTypography.bodyM.copyWith(color: AppColors.textTertiary),
      );
}

class _LinkRow extends StatelessWidget {
  final IconData icon;
  final String text;
  final VoidCallback onTap;
  const _LinkRow({super.key, required this.icon, required this.text, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
        child: Row(
          children: [
            Icon(icon, size: 16, color: AppColors.info),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                text,
                style: AppTypography.bodyM.copyWith(
                  color: AppColors.info,
                  decoration: TextDecoration.underline,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
