import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';
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
import '../../ai_chat/providers/chat_provider.dart';
import '../../location/domain/geo_distance.dart';
import '../../location/providers/user_location_provider.dart';
import '../../map/data/place_model.dart';
import '../data/navigation_service.dart';
import '../data/review_repository.dart';
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

void _showExternalErrorSnackBar(
  BuildContext context,
  String message, {
  bool clearBottomCta = false,
}) {
  if (!context.mounted) return;
  final bottomInset = MediaQuery.of(context).padding.bottom;
  ScaffoldMessenger.of(context)
    ..removeCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        content: Text(message),
        behavior: SnackBarBehavior.floating,
        margin: EdgeInsets.fromLTRB(
          16,
          0,
          16,
          clearBottomCta ? 104 + bottomInset : 16,
        ),
      ),
    );
}

Future<void> _openExternal(
  BuildContext context,
  WidgetRef ref,
  String rawUrl, {
  required bool clearBottomCta,
}) async {
  final opened = await openExternalUrlString(
    rawUrl,
    opener: ref.read(externalUriOpenerProvider),
  );
  if (!opened && context.mounted) {
    _showExternalErrorSnackBar(
      context,
      externalLinkOpenFailedText,
      clearBottomCta: clearBottomCta,
    );
  }
}

/// Unified "Chỉ đường": external map/navigation app with the place's
/// coordinates; the user's real position is the origin only when known.
Future<void> _openDirections(
  BuildContext context,
  WidgetRef ref,
  PlaceModel p,
  LatLng? origin,
) async {
  if (!p.hasCoordinates) {
    _showExternalErrorSnackBar(context, directionsOpenFailedText);
    return;
  }
  final openedUri = await openDirections(
    destLat: p.latitude!,
    destLng: p.longitude!,
    origin: origin,
    opener: ref.read(externalUriOpenerProvider),
  );
  if (openedUri == null && context.mounted) {
    _showExternalErrorSnackBar(
      context,
      directionsOpenFailedText,
      clearBottomCta: true,
    );
  }
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
      backgroundColor: AppColors.warmBackground,
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
        data: (place) {
          final user = ref.watch(userLocationProvider).position;
          return PlaceDetailView(
            place: place,
            distanceKm:
                distanceFromUserKm(user, place.latitude, place.longitude),
            onOpenUrl: (url) => _openExternal(
              context,
              ref,
              url,
              clearBottomCta: place.hasCoordinates,
            ),
            onDirections: () => _openDirections(context, ref, place, user),
            onEnableLocation: () =>
                ref.read(userLocationProvider.notifier).request(),
            onAskWandy: () {
              final dest = place.destinationName;
              final prompt = dest != null && dest.isNotEmpty
                  ? 'Gợi ý thông tin và lịch trình ghé thăm ${place.name} tại $dest.'
                  : 'Gợi ý thông tin và lịch trình ghé thăm ${place.name}.';
              ref.read(pendingChatPromptProvider.notifier).state = prompt;
              context.go('/ai');
            },
            onWriteReview: () => _openReviewSheet(context, ref, place),
          );
        },
      ),
    );
  }

  Future<void> _openReviewSheet(
    BuildContext context,
    WidgetRef ref,
    PlaceModel place,
  ) async {
    double selectedRating = 5.0;
    final controller = TextEditingController();
    bool isSubmitting = false;
    String? submitError;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (ctx, setSheetState) {
            return Padding(
              padding: EdgeInsets.fromLTRB(
                AppSpacing.screenHorizontal,
                AppSpacing.md,
                AppSpacing.screenHorizontal,
                MediaQuery.of(ctx).viewInsets.bottom + AppSpacing.md,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Đánh giá ${place.name}', style: AppTypography.h3),
                  const SizedBox(height: AppSpacing.sm),
                  Row(
                    children: List.generate(5, (i) {
                      final star = i + 1.0;
                      return IconButton(
                        key: Key('review_star_${i + 1}'),
                        icon: Icon(
                          star <= selectedRating ? Icons.star : Icons.star_border,
                          color: AppColors.warning,
                          size: 30,
                        ),
                        onPressed: isSubmitting
                            ? null
                            : () => setSheetState(() => selectedRating = star),
                      );
                    }),
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  TextField(
                    key: const Key('review_content_input'),
                    controller: controller,
                    maxLines: 3,
                    enabled: !isSubmitting,
                    decoration: const InputDecoration(
                      hintText: 'Chia sẻ trải nghiệm thực tế của bạn...',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  if (submitError != null) ...[
                    const SizedBox(height: AppSpacing.xs),
                    Text(
                      submitError!,
                      style: AppTypography.bodyS.copyWith(color: AppColors.error),
                    ),
                  ],
                  const SizedBox(height: AppSpacing.md),
                  SizedBox(
                    width: double.infinity,
                    child: AppButton(
                      key: const Key('review_submit_button'),
                      text: isSubmitting ? 'Đang gửi...' : 'Gửi đánh giá',
                      onPressed: isSubmitting
                          ? null
                          : () async {
                              if (controller.text.trim().length < 4) {
                                setSheetState(() => submitError =
                                    'Vui lòng nhập nhận xét tối thiểu 4 ký tự.');
                                return;
                              }
                              setSheetState(() {
                                isSubmitting = true;
                                submitError = null;
                              });
                              try {
                                await ref
                                    .read(reviewRepositoryProvider)
                                    .createReview(
                                      placeId: place.id,
                                      rating: selectedRating,
                                      content: controller.text,
                                    );
                                if (sheetContext.mounted) {
                                  Navigator.of(sheetContext).pop();
                                }
                                ref.invalidate(placeDetailProvider(place.id));
                                if (context.mounted) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text('Đã ghi nhận đánh giá thực tế của bạn!'),
                                    ),
                                  );
                                }
                              } on DioException catch (e) {
                                setSheetState(() {
                                  isSubmitting = false;
                                  submitError = e.response?.statusCode == 401
                                      ? 'Vui lòng đăng nhập lại để gửi đánh giá.'
                                      : 'Không thể gửi đánh giá lúc này.';
                                });
                              } catch (_) {
                                setSheetState(() {
                                  isSubmitting = false;
                                  submitError = 'Không thể gửi đánh giá lúc này.';
                                });
                              }
                            },
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
    controller.dispose();
  }
}

/// Pure presentation of a place's factual data. Unavailable fields render an
/// honest "not available" state or are omitted — never invented.
class PlaceDetailView extends StatelessWidget {
  final PlaceModel place;

  /// Real distance from the user's current position; `null` = unknown.
  final double? distanceKm;
  final void Function(String url) onOpenUrl;
  final VoidCallback onDirections;
  final VoidCallback? onEnableLocation;
  final VoidCallback? onAskWandy;
  final VoidCallback? onWriteReview;

  const PlaceDetailView({
    super.key,
    required this.place,
    this.distanceKm,
    required this.onOpenUrl,
    required this.onDirections,
    this.onEnableLocation,
    this.onAskWandy,
    this.onWriteReview,
  });

  @override
  Widget build(BuildContext context) {
    final catColor = AppColors.forCategory(place.categoryName);
    final hasHours = place.openingHours != null;
    final hasContact = place.website != null || place.phone != null;
    final galleryUrls = <String>{
      if (place.coverImage != null) place.coverImage!,
      ...place.images,
    }.where((u) => u.startsWith('http')).toList();

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

                  // ── Curated Gallery (Wikimedia Commons / OSM verified URLs) ──
                  if (galleryUrls.isNotEmpty) ...[
                    SizedBox(
                      key: const Key('place_detail_gallery'),
                      height: 172,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: galleryUrls.length,
                        separatorBuilder: (_, __) =>
                            const SizedBox(width: AppSpacing.sm),
                        itemBuilder: (_, idx) => ClipRRect(
                          borderRadius: AppRadius.cardRadius,
                          child: Container(
                            width: 256,
                            color: AppColors.surfaceContainer,
                            child: Image.network(
                              galleryUrls[idx],
                              fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => Center(
                                child: Icon(
                                  placeCategoryIcon(place.categoryName),
                                  size: 36,
                                  color: catColor.withValues(alpha: 0.6),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                    if (place.enrichmentMeta?.firstImageLicense != null) ...[
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'Ảnh nguồn Wikimedia Commons (${place.enrichmentMeta!.firstImageLicense!})',
                        style: AppTypography.bodyS
                            .copyWith(color: AppColors.textTertiary),
                      ),
                    ],
                    const SizedBox(height: AppSpacing.md),
                  ],

                  // ── Rating & Traveler Reviews ──
                  _Section(
                    icon: Icons.star_border,
                    title: 'Đánh giá',
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: RatingView(
                                rating: place.rating,
                                reviewCount: place.reviewCount,
                                iconSize: 18,
                              ),
                            ),
                            if (onWriteReview != null)
                              TextButton.icon(
                                key: const Key('place_detail_write_review'),
                                onPressed: onWriteReview,
                                icon: const Icon(Icons.rate_review_outlined,
                                    size: 16),
                                label: const Text('Viết đánh giá'),
                              ),
                          ],
                        ),
                        if (place.reviews.isNotEmpty) ...[
                          const Divider(height: AppSpacing.md),
                          for (final rev in place.reviews.take(5))
                            Padding(
                              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Text(
                                        rev.authorName,
                                        style: AppTypography.label.copyWith(
                                          fontWeight: FontWeight.w700,
                                        ),
                                      ),
                                      const SizedBox(width: AppSpacing.xs),
                                      const Icon(Icons.star,
                                          size: 14, color: AppColors.warning),
                                      const SizedBox(width: 2),
                                      Text(
                                        rev.rating.toStringAsFixed(1),
                                        style: AppTypography.bodyS,
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 2),
                                  Text(rev.content, style: AppTypography.bodyS),
                                ],
                              ),
                            ),
                        ],
                      ],
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
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(place.description!, style: AppTypography.bodyM),
                          if (place.enrichmentMeta?.descriptionSourceUrl !=
                              null) ...[
                            const SizedBox(height: AppSpacing.xs),
                            _LinkRow(
                              key: const Key('place_detail_wiki_source'),
                              icon: Icons.menu_book_outlined,
                              text:
                                  'Nguồn tham khảo (${place.enrichmentMeta!.descriptionLicense ?? 'CC BY-SA 4.0'})',
                              onTap: () => onOpenUrl(
                                place.enrichmentMeta!.descriptionSourceUrl!,
                              ),
                            ),
                          ],
                        ],
                      ),
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
                          const SizedBox(height: AppSpacing.xs),
                          Wrap(
                            spacing: AppSpacing.sm,
                            runSpacing: AppSpacing.xs,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.near_me,
                                      size: 14,
                                      color: distanceKm == null
                                          ? AppColors.textTertiary
                                          : AppColors.primary),
                                  const SizedBox(width: AppSpacing.xs),
                                  Flexible(
                                    child: Text(
                                      distanceLabel(distanceKm),
                                      key: const Key('place_detail_distance'),
                                      style: AppTypography.bodyS.copyWith(
                                          color: distanceKm == null
                                              ? AppColors.textTertiary
                                              : AppColors.primary,
                                          fontWeight: FontWeight.w600),
                                    ),
                                  ),
                                ],
                              ),
                              if (distanceKm == null && onEnableLocation != null)
                                InkWell(
                                  key: const Key('place_detail_enable_location'),
                                  onTap: onEnableLocation,
                                  borderRadius: AppRadius.smRadius,
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 6, vertical: 2),
                                    child: Text(
                                      'Bật vị trí',
                                      style: AppTypography.label.copyWith(
                                        color: AppColors.primary,
                                        decoration: TextDecoration.underline,
                                      ),
                                    ),
                                  ),
                                ),
                            ],
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
          if (place.hasCoordinates || onAskWandy != null)
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
                border: Border(top: BorderSide(color: AppColors.softBorder)),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (place.hasCoordinates) ...[
                    Text(
                      navigationHintText,
                      key: const Key('place_detail_nav_hint'),
                      style: AppTypography.bodyS
                          .copyWith(color: AppColors.textTertiary),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                  ],
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final textScale = MediaQuery.textScalerOf(context).scale(1);
                      final stackActions = place.hasCoordinates &&
                          onAskWandy != null &&
                          (constraints.maxWidth < 380 || textScale > 1.15);
                      final wandyButton = onAskWandy == null
                          ? null
                          : AppButton(
                              key: const Key('place_detail_ask_wandy'),
                              text: 'Hỏi Wandy',
                              icon: Icons.auto_awesome_outlined,
                              variant: AppButtonVariant.secondary,
                              onPressed: onAskWandy,
                            );
                      final directionsButton = place.hasCoordinates
                          ? AppButton(
                              key: const Key('place_detail_directions'),
                              text: 'Chỉ đường',
                              icon: Icons.directions,
                              onPressed: onDirections,
                            )
                          : null;

                      if (stackActions) {
                        return Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            directionsButton!,
                            const SizedBox(height: AppSpacing.xs),
                            wandyButton!,
                          ],
                        );
                      }

                      if (wandyButton != null && directionsButton != null) {
                        return Row(
                          children: [
                            Expanded(child: wandyButton),
                            const SizedBox(width: AppSpacing.sm),
                            Expanded(flex: 2, child: directionsButton),
                          ],
                        );
                      }

                      return directionsButton ?? wandyButton!;
                    },
                  ),
                ],
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
          border: Border.all(color: AppColors.softBorder),
          boxShadow: [
            BoxShadow(
              color: AppColors.primaryDeep.withValues(alpha: 0.04),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 18, color: AppColors.primary),
                const SizedBox(width: AppSpacing.sm),
                Flexible(
                  child: Text(
                    title,
                    style: AppTypography.h3.copyWith(fontSize: 15),
                  ),
                ),
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
