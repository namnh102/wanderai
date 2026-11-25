import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_badge.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/app_loading.dart';
import '../../../../core/widgets/app_state_banner.dart';
import '../../../map/data/place_model.dart';
import '../../data/youtube_update_model.dart';
import '../../providers/place_detail_provider.dart';

/// Displays YouTube community freshness updates (`DYNAMIC_SOCIAL_FRESHNESS_LAYER`)
/// cleanly separated from factual OSM/Wikipedia POI data.
///
/// Errors and loading states are strictly non-blocking so the rest of
/// [PlaceDetailScreen] and [SavePlaceToTripSheet] remain fully usable.
class YoutubeFreshnessSection extends ConsumerStatefulWidget {
  final PlaceModel place;
  final void Function(String url) onOpenUrl;

  const YoutubeFreshnessSection({
    super.key,
    required this.place,
    required this.onOpenUrl,
  });

  @override
  ConsumerState<YoutubeFreshnessSection> createState() =>
      _YoutubeFreshnessSectionState();
}

class _YoutubeFreshnessSectionState
    extends ConsumerState<YoutubeFreshnessSection> {
  static final DateFormat _timestampFormat = DateFormat('dd/MM/yyyy HH:mm:ss');

  YoutubeUpdatesEnvelope? _capturedEnvelope;
  DateTime? _renderedAt;

  DateTime _resolveRenderedAt(YoutubeUpdatesEnvelope envelope) {
    if (!identical(_capturedEnvelope, envelope) || _renderedAt == null) {
      _capturedEnvelope = envelope;
      _renderedAt = ref.read(youtubeClockProvider)().toUtc();
    }
    return _renderedAt!;
  }

  String _resolveCityName(YoutubeUpdatesEnvelope envelope) {
    final envCity = envelope.destinationName?.trim();
    if (envCity != null && envCity.isNotEmpty) return envCity;
    final placeCity = widget.place.destinationName?.trim();
    if (placeCity != null && placeCity.isNotEmpty) return placeCity;
    return 'Hạ Long';
  }

  @override
  Widget build(BuildContext context) {
    final updatesAsync = ref.watch(placeYoutubeUpdatesProvider(widget.place.id));
    final envelope = updatesAsync.valueOrNull;
    final governanceRole =
        envelope?.governanceRole ?? YoutubeUpdatesEnvelope.defaultGovernanceRole;
    final showSeparationNote = envelope?.notPrimaryFactualCorpus ?? true;

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.mdSmall),
      child: AppCard(
        key: const Key('place_youtube_freshness_section'),
        borderRadius: AppRadius.cardRadius,
        border: const BorderSide(color: AppColors.softBorder),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.ondemand_video_rounded,
                  size: 18,
                  color: AppColors.accentCoral,
                ),
                const SizedBox(width: AppSpacing.sm),
                Flexible(
                  child: Text(
                    'Cập nhật cộng đồng từ YouTube',
                    style: AppTypography.h3.copyWith(fontSize: 15),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            const Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                AppBadge(
                  key: Key('youtube_governance_badge'),
                  label: 'Cập nhật xã hội · YouTube',
                  icon: Icons.dynamic_feed_rounded,
                  color: AppColors.onAccentCoral,
                  backgroundColor: AppColors.accentCoralContainer,
                ),
              ],
            ),
            if (showSeparationNote) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Tầng $governanceRole — Nguồn cộng đồng tham khảo, tách biệt khỏi dữ liệu xác minh OSM/Wikipedia.',
                key: const Key('youtube_governance_note'),
                style: AppTypography.bodyS.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.sm),
            updatesAsync.when(
              loading: () => const AppLoading(
                key: Key('youtube_updates_loading'),
                isCompact: true,
                message: 'Đang tải cập nhật cộng đồng từ YouTube...',
              ),
              error: (err, _) {
                final statusCode =
                    err is DioException ? err.response?.statusCode : null;
                if (statusCode == 404) {
                  return Text(
                    'Chưa có cập nhật YouTube nào được xác minh cho địa điểm này.',
                    key: const Key('youtube_updates_empty'),
                    style: AppTypography.bodyS.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  );
                }
                return AppStateBanner(
                  key: const Key('youtube_updates_error_banner'),
                  tone: AppStateBannerTone.warning,
                  message: 'Không thể tải cập nhật YouTube lúc này.',
                  actionLabel: 'Thử lại',
                  onAction: () {
                    _capturedEnvelope = null;
                    _renderedAt = null;
                    ref.invalidate(
                        placeYoutubeUpdatesProvider(widget.place.id));
                  },
                );
              },
              data: (data) {
                final renderedAt = _resolveRenderedAt(data);
                if (data.items.isEmpty && data.cityFallbackItems.isEmpty) {
                  return Text(
                    'Chưa có cập nhật YouTube nào được xác minh cho địa điểm này.',
                    key: const Key('youtube_updates_empty'),
                    style: AppTypography.bodyS.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  );
                }

                final cityName = _resolveCityName(data);
                final cityFallbackLabel = 'Cập nhật cấp thành phố: $cityName';

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (var i = 0; i < data.items.length; i++) ...[
                      if (i > 0) const SizedBox(height: AppSpacing.sm),
                      _YoutubeUpdateItemCard(
                        item: data.items[i],
                        renderedAt: renderedAt,
                        slaMaxLatencyMs: data.realtimeSlaMaxLatencyMs,
                        timestampFormat: _timestampFormat,
                        onOpenUrl: widget.onOpenUrl,
                      ),
                    ],
                    if (data.cityFallbackItems.isNotEmpty) ...[
                      if (data.items.isNotEmpty) ...[
                        const SizedBox(height: AppSpacing.md),
                        Text(
                          cityFallbackLabel,
                          key: const Key('youtube_city_fallback_subheader'),
                          style: AppTypography.label.copyWith(
                            color: AppColors.info,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: AppSpacing.xs),
                      ] else ...[
                        AppStateBanner(
                          key: const Key('youtube_city_fallback_banner'),
                          tone: AppStateBannerTone.info,
                          icon: Icons.location_city,
                          message:
                              'Chưa có cập nhật riêng cho địa điểm này · $cityFallbackLabel',
                        ),
                        const SizedBox(height: AppSpacing.sm),
                      ],
                      for (var i = 0;
                          i < data.cityFallbackItems.length;
                          i++) ...[
                        if (i > 0) const SizedBox(height: AppSpacing.sm),
                        _YoutubeUpdateItemCard(
                          item: data.cityFallbackItems[i],
                          renderedAt: renderedAt,
                          slaMaxLatencyMs: data.realtimeSlaMaxLatencyMs,
                          timestampFormat: _timestampFormat,
                          cityFallbackLabel: cityFallbackLabel,
                          onOpenUrl: widget.onOpenUrl,
                        ),
                      ],
                    ],
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _YoutubeUpdateItemCard extends StatelessWidget {
  final YoutubeUpdateModel item;
  final DateTime renderedAt;
  final int slaMaxLatencyMs;
  final DateFormat timestampFormat;
  final String? cityFallbackLabel;
  final void Function(String url) onOpenUrl;

  const _YoutubeUpdateItemCard({
    required this.item,
    required this.renderedAt,
    required this.slaMaxLatencyMs,
    required this.timestampFormat,
    this.cityFallbackLabel,
    required this.onOpenUrl,
  });

  String _formatLatency(int ms) {
    if (ms < 0) return '$ms ms (lệch đồng hồ)';
    if (ms < 1000) return '$ms ms';
    if (ms < 60000) {
      return '${(ms / 1000).toStringAsFixed(1)}s ($ms ms)';
    }
    final minutes = ms / 60000;
    return '${minutes.toStringAsFixed(1)} phút (${(ms / 1000).round()}s)';
  }

  @override
  Widget build(BuildContext context) {
    final endToEndMs = item.endToEndLatencyMsAt(renderedAt);
    final isRealtime = item.isRealtimeAt(
      renderedAt,
      slaMaxLatencyMs: slaMaxLatencyMs,
    );
    final badgeLabel = item.freshnessBadgeLabelAt(
      renderedAt,
      slaMaxLatencyMs: slaMaxLatencyMs,
    );
    final channelDisplay = (item.channelTitle?.trim().isNotEmpty == true)
        ? item.channelTitle!.trim()
        : (item.channelId.isNotEmpty ? item.channelId : 'YouTube');

    return AppCard(
      key: Key('youtube_update_card_${item.id}'),
      padding: const EdgeInsets.all(AppSpacing.sm),
      backgroundColor: AppColors.warmSurface,
      border: const BorderSide(color: AppColors.softBorder),
      onTap: item.videoUrl.isNotEmpty ? () => onOpenUrl(item.videoUrl) : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              AppBadge(
                key: Key('youtube_freshness_badge_${item.id}'),
                label: badgeLabel,
                icon: isRealtime ? Icons.bolt_rounded : Icons.schedule_rounded,
                color: isRealtime ? AppColors.success : AppColors.textSecondary,
                backgroundColor: isRealtime
                    ? AppColors.successContainer
                    : AppColors.surfaceContainer,
              ),
              if (item.isCityLevel)
                AppBadge(
                  key: Key('youtube_city_badge_${item.id}'),
                  label: cityFallbackLabel ?? 'Cập nhật cấp thành phố',
                  icon: Icons.location_city,
                  color: AppColors.info,
                  backgroundColor: AppColors.infoContainer,
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            item.title,
            style: AppTypography.label.copyWith(
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            item.placeId != null
                ? 'place_id: ${item.placeId}'
                : 'place_id: null (cấp thành phố)',
            key: Key('youtube_place_id_${item.id}'),
            style: AppTypography.caption.copyWith(
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            'Nguồn: ${item.source} · $channelDisplay',
            key: Key('youtube_source_${item.id}'),
            style: AppTypography.bodyS.copyWith(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w600,
            ),
          ),
          if (item.videoUrl.isNotEmpty) ...[
            const SizedBox(height: 2),
            InkWell(
              key: Key('youtube_video_link_${item.id}'),
              onTap: () => onOpenUrl(item.videoUrl),
              borderRadius: AppRadius.smRadius,
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Row(
                  children: [
                    const Icon(
                      Icons.open_in_new,
                      size: 14,
                      color: AppColors.info,
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Expanded(
                      child: Text(
                        item.videoUrl,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: AppTypography.bodyS.copyWith(
                          color: AppColors.info,
                          decoration: TextDecoration.underline,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
          const SizedBox(height: 2),
          Text(
            item.hasValidPublishedAt
                ? 'Xuất bản: ${timestampFormat.format(item.publishedAt.toLocal())}'
                : 'Xuất bản: Không rõ thời điểm xuất bản',
            key: Key('youtube_published_at_${item.id}'),
            style: AppTypography.caption.copyWith(color: AppColors.textSecondary),
          ),
          Text(
            item.hasValidReceivedAt
                ? 'Tiếp nhận: ${timestampFormat.format(item.receivedAt.toLocal())}'
                : 'Tiếp nhận: Không rõ thời điểm tiếp nhận',
            key: Key('youtube_received_at_${item.id}'),
            style: AppTypography.caption.copyWith(color: AppColors.textSecondary),
          ),
          Text(
            (item.hasValidReceivedAt ||
                    item.sourceUpdatedAt != null ||
                    item.lastReceivedAt != null)
                ? 'Cập nhật: ${timestampFormat.format(item.updatedAt.toLocal())}'
                : 'Cập nhật: Không rõ thời điểm cập nhật',
            key: Key('youtube_updated_at_${item.id}'),
            style: AppTypography.caption.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            item.hasReliableTiming
                ? 'Độ trễ nguồn tới app: ${_formatLatency(endToEndMs)} · '
                    'Tiếp nhận server: ${_formatLatency(item.ingestLatencyMs)}'
                : 'Độ trễ nguồn tới app: Không xác định (thiếu mốc thời gian hợp lệ)',
            key: Key('youtube_latency_${item.id}'),
            style: AppTypography.caption.copyWith(
              color: isRealtime ? AppColors.success : AppColors.textSecondary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}
