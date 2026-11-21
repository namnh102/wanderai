import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_button.dart';
import '../../../../core/widgets/app_empty_state.dart';
import '../../../../core/widgets/app_error_state.dart';
import '../../../../core/widgets/app_loading.dart';
import '../../../../core/widgets/responsive_wrapper.dart';
import '../../../location/providers/user_location_provider.dart';
import '../../../map/data/destination_model.dart';
import '../../../map/data/place_model.dart';
import '../../../map/providers/map_provider.dart';
import '../../data/home_models.dart';
import 'home_verified_place_tile.dart';

/// Opens a destination preview sheet loading verified places from `GET /places`
/// so every destination card on Home provides real interactive discovery.
Future<void> showDestinationPlacesSheet(
  BuildContext context, {
  required HomeDestinationItem destination,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    builder: (ctx) => _DestinationPlacesSheet(destination: destination),
  );
}

class _DestinationPlacesSheet extends ConsumerStatefulWidget {
  final HomeDestinationItem destination;

  const _DestinationPlacesSheet({required this.destination});

  @override
  ConsumerState<_DestinationPlacesSheet> createState() =>
      _DestinationPlacesSheetState();
}

class _DestinationPlacesSheetState
    extends ConsumerState<_DestinationPlacesSheet> {
  bool _loading = true;
  String? _error;
  List<PlaceModel> _places = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final repo = ref.read(placeRepositoryProvider);
      final items = await repo.getPlaces(
        destinationId: widget.destination.id,
        verifiedOnly: true,
        limit: 20,
      );
      if (!mounted) return;
      setState(() {
        _places = items;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Không thể tải danh sách địa điểm của ${widget.destination.name}.';
        _loading = false;
      });
    }
  }

  void _openOnMap(BuildContext context) {
    final notifier = ref.read(mapProvider.notifier);
    final isMapSupported = supportedDestinations.any(
      (d) => d.slug == widget.destination.slug,
    );
    Navigator.of(context).pop();
    if (isMapSupported) {
      notifier.selectDestination(widget.destination.slug);
    } else {
      notifier.searchPlaces(widget.destination.name);
    }
    context.go('/map');
  }

  @override
  Widget build(BuildContext context) {
    final userPos = ref.watch(userLocationProvider).position;
    final maxHeight = MediaQuery.of(context).size.height * 0.78;

    return ResponsiveWrapper(
      maxWidth: 640.0,
      fillHeight: false,
      child: Container(
        constraints: BoxConstraints(maxHeight: maxHeight),
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: AppRadius.sheetRadius,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: AppSpacing.sm),
            Center(
              child: Container(
                width: 40,
                height: 4,
                decoration: const BoxDecoration(
                  color: AppColors.border,
                  borderRadius: AppRadius.pillRadius,
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(
                AppSpacing.md,
                AppSpacing.mdSmall,
                AppSpacing.sm,
                AppSpacing.sm,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.destination.name,
                          style: AppTypography.h2,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${widget.destination.province} · ${widget.destination.regionLabel}',
                          style: AppTypography.caption,
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Đóng',
                    icon: const Icon(Icons.close_rounded),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                ],
              ),
            ),
            if (widget.destination.description != null &&
                widget.destination.description!.trim().isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.md,
                  0,
                  AppSpacing.md,
                  AppSpacing.sm,
                ),
                child: Text(
                  widget.destination.description!,
                  style: AppTypography.bodyM,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            const Divider(),
            Expanded(
              child: _loading
                  ? const AppLoading(message: 'Đang tải địa điểm xác minh...')
                  : _error != null
                      ? AppErrorState(message: _error!, onRetry: _load)
                      : _places.isEmpty
                          ? const AppEmptyState(
                              icon: Icons.location_searching_outlined,
                              title: 'Chưa có địa điểm xác minh',
                              description:
                                  'Chưa có địa điểm từ nguồn OpenStreetMap cho điểm đến này.',
                            )
                          : ListView.separated(
                              padding: const EdgeInsets.all(AppSpacing.md),
                              itemCount: _places.length,
                              separatorBuilder: (_, __) =>
                                  const SizedBox(height: AppSpacing.sm),
                              itemBuilder: (ctx, idx) {
                                final place = _places[idx];
                                return HomeVerifiedPlaceTile(
                                  place: place,
                                  userPosition: userPos,
                                  onTap: () {
                                    Navigator.of(context).pop();
                                    context.push('/places/${place.id}');
                                  },
                                );
                              },
                            ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.md,
                  AppSpacing.sm,
                  AppSpacing.md,
                  AppSpacing.md,
                ),
                child: AppButton(
                  text: 'Mở trên Bản đồ',
                  icon: Icons.map_outlined,
                  onPressed: () => _openOnMap(context),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
