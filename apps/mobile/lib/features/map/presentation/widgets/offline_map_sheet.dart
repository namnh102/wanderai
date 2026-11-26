import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_button.dart';
import '../../../../core/widgets/app_state_banner.dart';
import '../../data/offline_map_models.dart';
import '../../providers/map_provider.dart';

Future<void> showOfflineMapSheet(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.surface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (_) => const OfflineMapSheet(),
  );
}

class OfflineMapSheet extends ConsumerWidget {
  const OfflineMapSheet({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(mapProvider);
    final notifier = ref.read(mapProvider.notifier);
    final cached = state.cachedHalongRegion;
    final progress = state.offlineProgress;
    final expectedTiles = enumerateTilesForBounds(
      halongOfflineRegionPreset.bounds,
      halongOfflineRegionPreset.minZoom,
      halongOfflineRegionPreset.maxZoom,
    ).length;

    return SafeArea(
      top: false,
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          AppSpacing.mdSmall,
          AppSpacing.md,
          AppSpacing.lg,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: AppSpacing.mdSmall),
                decoration: const BoxDecoration(
                  color: AppColors.softBorder,
                  borderRadius: AppRadius.pillRadius,
                ),
              ),
            ),
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: const BoxDecoration(
                    color: AppColors.primaryContainer,
                    borderRadius: AppRadius.smRadius,
                  ),
                  child: const Icon(
                    Icons.offline_pin_outlined,
                    color: AppColors.primaryDeep,
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Bản đồ ngoại tuyến', style: AppTypography.h3),
                      Text(
                        halongOfflineRegionPreset.name,
                        style: AppTypography.bodyS.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),

            // Metadata box
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AppSpacing.mdSmall),
              decoration: BoxDecoration(
                color: AppColors.surfaceContainer,
                borderRadius: AppRadius.mdRadius,
                border: Border.all(color: AppColors.softBorder),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _InfoRow(
                    label: 'Phạm vi',
                    value: halongOfflineRegionPreset.bounds.formattedLabel,
                  ),
                  const SizedBox(height: 6),
                  _InfoRow(
                    label: 'Mức zoom',
                    value:
                        'z${halongOfflineRegionPreset.minZoom} – z${halongOfflineRegionPreset.maxZoom} ($expectedTiles mảnh)',
                  ),
                  const SizedBox(height: 6),
                  const _InfoRow(
                    label: 'Nguồn tile',
                    value: 'OSM HOT / OSM France',
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.mdSmall),

            // Cache status / progress
            if (state.isDownloadingOffline) ...[
              Container(
                key: const Key('offline_download_progress'),
                width: double.infinity,
                padding: const EdgeInsets.all(AppSpacing.mdSmall),
                decoration: BoxDecoration(
                  color: AppColors.primaryContainer.withValues(alpha: 0.35),
                  borderRadius: AppRadius.mdRadius,
                  border: Border.all(
                    color: AppColors.primary.withValues(alpha: 0.3),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Đang tải ${progress?.completedTiles ?? 0}/${progress?.totalTiles ?? expectedTiles} mảnh...',
                      style: AppTypography.label.copyWith(
                        color: AppColors.primaryDeep,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                      value: progress?.fraction ?? 0.0,
                      backgroundColor: AppColors.softBorder,
                      color: AppColors.primary,
                    ),
                    const SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: notifier.cancelOfflineDownload,
                        child: const Text('Hủy tải'),
                      ),
                    ),
                  ],
                ),
              ),
            ] else if (cached != null) ...[
              Container(
                key: const Key('offline_cache_summary'),
                width: double.infinity,
                padding: const EdgeInsets.all(AppSpacing.mdSmall),
                decoration: BoxDecoration(
                  color: AppColors.primaryContainer.withValues(alpha: 0.35),
                  borderRadius: AppRadius.mdRadius,
                  border: Border.all(
                    color: AppColors.primary.withValues(alpha: 0.3),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          cached.isComplete
                              ? Icons.check_circle_outline
                              : Icons.info_outline,
                          size: 16,
                          color: AppColors.primaryDeep,
                        ),
                        const SizedBox(width: 6),
                        Flexible(
                          child: Text(
                            cached.isComplete
                                ? 'Đã lưu ngoại tuyến'
                                : 'Đã lưu một phần',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: AppTypography.label.copyWith(
                              color: AppColors.primaryDeep,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    _InfoRow(
                      label: 'Số mảnh',
                      value: '${cached.tileCount}/${cached.expectedTileCount} mảnh',
                    ),
                    const SizedBox(height: 4),
                    _InfoRow(
                      label: 'Dung lượng',
                      value: cached.formattedSize,
                    ),
                    const SizedBox(height: 4),
                    _InfoRow(
                      label: 'Địa điểm đã lưu',
                      value: '${cached.places.length} địa điểm',
                    ),
                  ],
                ),
              ),
            ] else ...[
              const AppStateBanner(
                message:
                    'Chưa tải vùng Hạ Long ngoại tuyến. Tải trước để xem bản đồ & địa điểm khi mất mạng.',
                tone: AppStateBannerTone.info,
              ),
            ],

            if (state.offlineError != null) ...[
              const SizedBox(height: AppSpacing.sm),
              AppStateBanner(
                message: state.offlineError!,
                tone: AppStateBannerTone.error,
              ),
            ],

            const SizedBox(height: AppSpacing.md),

            SizedBox(
              width: double.infinity,
              child: AppButton(
                key: const Key('offline_download_button'),
                text: cached != null
                    ? 'Cập nhật / Kiểm tra lại'
                    : 'Tải bản đồ ngoại tuyến',
                icon: Icons.download_for_offline_outlined,
                onPressed: state.isDownloadingOffline
                    ? null
                    : () => notifier.downloadHalongOfflineRegion(),
              ),
            ),

            if (cached != null && !state.isDownloadingOffline) ...[
              const SizedBox(height: AppSpacing.sm),
              Row(
                children: [
                  Expanded(
                    flex: 3,
                    child: OutlinedButton.icon(
                      key: const Key('offline_recenter_button'),
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size(0, 44),
                      ),
                      onPressed: () {
                        notifier.recenterToOfflineRegion();
                        Navigator.of(context).pop();
                      },
                      icon: const Icon(Icons.center_focus_strong, size: 18),
                      label: const Text('Về vùng Hạ Long'),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    flex: 2,
                    child: OutlinedButton.icon(
                      key: const Key('offline_delete_button'),
                      onPressed: () => notifier.deleteHalongOfflineRegion(),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.error,
                        minimumSize: const Size(0, 44),
                        side: const BorderSide(
                          color: AppColors.error,
                          width: 1.5,
                        ),
                      ),
                      icon: const Icon(Icons.delete_outline, size: 18),
                      label: const Text('Xóa cache'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 112,
          child: Text(
            label,
            style: AppTypography.bodyS.copyWith(color: AppColors.textSecondary),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: AppTypography.bodyS.copyWith(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    );
  }
}
