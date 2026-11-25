import 'dart:async';
import 'dart:math' as math;
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
import '../../../../core/widgets/app_search_bar.dart';
import '../../../../core/widgets/responsive_wrapper.dart';
import '../../../location/providers/user_location_provider.dart';
import '../../../map/data/destination_model.dart';
import '../../../map/data/place_model.dart';
import '../../../map/providers/map_provider.dart';
import '../../data/home_models.dart';
import 'home_verified_place_tile.dart';

/// Opens a destination preview sheet loading verified places from `GET /places`
/// (with destination-scoped search) so every destination card on Home provides
/// real interactive discovery across the entire destination catalog.
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
  static const int _pageSize = 20;
  final TextEditingController _searchCtrl = TextEditingController();
  final ScrollController _scrollCtrl = ScrollController();
  Timer? _debounce;
  int _loadSeq = 0;
  int _page = 1;
  bool _hasMore = false;
  bool _loadingMore = false;
  String _activeSearch = '';
  bool _loading = true;
  String? _error;
  List<PlaceModel> _places = const [];

  @override
  void initState() {
    super.initState();
    _scrollCtrl.addListener(_onScroll);
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _scrollCtrl.removeListener(_onScroll);
    _scrollCtrl.dispose();
    _searchCtrl.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollCtrl.hasClients || _loading || _loadingMore || !_hasMore) {
      return;
    }
    final pos = _scrollCtrl.position;
    if (pos.pixels >= pos.maxScrollExtent - 200) {
      _loadMore();
    }
  }

  void _onSearchChanged(String value) {
    setState(() {});
    _debounce?.cancel();
    final trimmed = value.trim();
    if (trimmed.isEmpty) {
      _load(search: '');
      return;
    }
    _debounce = Timer(
      const Duration(milliseconds: 300),
      () => _load(search: trimmed),
    );
  }

  Future<void> _load({String? search}) async {
    if (!mounted) return;
    final query = (search ?? _activeSearch).trim();
    final seq = ++_loadSeq;
    setState(() {
      _activeSearch = query;
      _page = 1;
      _hasMore = false;
      _loadingMore = false;
      _loading = true;
      _error = null;
    });
    try {
      final repo = ref.read(placeRepositoryProvider);
      final items = await repo.getPlaces(
        page: 1,
        destinationId: widget.destination.id,
        search: query.isEmpty ? null : query,
        verifiedOnly: true,
        limit: _pageSize,
      );
      if (!mounted || seq != _loadSeq) return;
      setState(() {
        _places = items;
        _hasMore = items.length >= _pageSize;
        _loading = false;
      });
    } catch (_) {
      if (!mounted || seq != _loadSeq) return;
      setState(() {
        _error =
            'Không thể tải danh sách địa điểm của ${widget.destination.name}.';
        _loading = false;
      });
    }
  }

  Future<void> _loadMore() async {
    if (!mounted || _loadingMore || !_hasMore) return;
    final seq = _loadSeq;
    final nextPage = _page + 1;
    setState(() => _loadingMore = true);
    try {
      final repo = ref.read(placeRepositoryProvider);
      final items = await repo.getPlaces(
        page: nextPage,
        destinationId: widget.destination.id,
        search: _activeSearch.isEmpty ? null : _activeSearch,
        verifiedOnly: true,
        limit: _pageSize,
      );
      if (!mounted || seq != _loadSeq) return;
      final existingIds = _places.map((p) => p.id).toSet();
      final appended =
          items.where((p) => !existingIds.contains(p.id)).toList();
      setState(() {
        _page = nextPage;
        _places = [..._places, ...appended];
        _hasMore = items.length >= _pageSize && appended.isNotEmpty;
        _loadingMore = false;
      });
    } catch (_) {
      if (!mounted || seq != _loadSeq) return;
      setState(() => _loadingMore = false);
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

  Widget _buildScrollableState(Widget child) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (!constraints.hasBoundedHeight) {
          return child;
        }
        return SingleChildScrollView(
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: constraints.maxHeight),
            child: child,
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final userPos = ref.watch(userLocationProvider).position;
    final mediaQuery = MediaQuery.of(context);
    final viewInsetsBottom = mediaQuery.viewInsets.bottom;
    final isKeyboardOpen = viewInsetsBottom > 0;
    final safeHeight = math.max(
      0.0,
      mediaQuery.size.height - mediaQuery.padding.top,
    );
    final maxHeight =
        isKeyboardOpen ? safeHeight : mediaQuery.size.height * 0.84;

    return ResponsiveWrapper(
      maxWidth: 640.0,
      fillHeight: false,
      child: Container(
        constraints: BoxConstraints(maxHeight: maxHeight),
        padding: EdgeInsets.only(bottom: viewInsetsBottom),
        decoration: const BoxDecoration(
          color: AppColors.surface,
          borderRadius: AppRadius.sheetRadius,
        ),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final useScrollFallback =
                constraints.hasBoundedHeight && constraints.maxHeight < 180;
            final bodyWidget = _loading
                ? _buildScrollableState(
                    const AppLoading(message: 'Đang tải địa điểm xác minh...'),
                  )
                : _error != null
                    ? _buildScrollableState(
                        AppErrorState(
                          message: _error!,
                          onRetry: () => _load(search: _activeSearch),
                        ),
                      )
                    : _places.isEmpty
                        ? _buildScrollableState(
                            AppEmptyState(
                              icon: _activeSearch.isNotEmpty
                                  ? Icons.search_off_rounded
                                  : Icons.location_searching_outlined,
                              title: _activeSearch.isNotEmpty
                                  ? 'Không tìm thấy địa điểm'
                                  : 'Chưa có địa điểm xác minh',
                              description: _activeSearch.isNotEmpty
                                  ? 'Chưa có địa điểm xác minh phù hợp với "$_activeSearch" tại ${widget.destination.name}.'
                                  : 'Chưa có địa điểm từ nguồn OpenStreetMap cho điểm đến này.',
                            ),
                          )
                        : ListView.separated(
                            controller: useScrollFallback ? null : _scrollCtrl,
                            shrinkWrap: useScrollFallback,
                            physics: useScrollFallback
                                ? const NeverScrollableScrollPhysics()
                                : null,
                            padding: const EdgeInsets.all(AppSpacing.md),
                            itemCount: _places.length + (_loadingMore ? 1 : 0),
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: AppSpacing.sm),
                            itemBuilder: (ctx, idx) {
                              if (idx >= _places.length) {
                                return const Padding(
                                  padding: EdgeInsets.symmetric(
                                    vertical: AppSpacing.sm,
                                  ),
                                  child: AppLoading(
                                    isCompact: true,
                                    message: 'Đang tải thêm địa điểm...',
                                  ),
                                );
                              }
                              final place = _places[idx];
                              return HomeVerifiedPlaceTile(
                                key: Key('dest_place_tile_${place.id}'),
                                place: place,
                                userPosition: userPos,
                                onTap: () {
                                  Navigator.of(context).pop();
                                  context.push('/places/${place.id}');
                                },
                              );
                            },
                          );

            final columnChildren = <Widget>[
              if (!useScrollFallback) ...[
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
              ],
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.md,
                  AppSpacing.mdSmall,
                  AppSpacing.sm,
                  AppSpacing.xs,
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
              if (!isKeyboardOpen &&
                  widget.destination.description != null &&
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
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.md,
                  0,
                  AppSpacing.md,
                  AppSpacing.sm,
                ),
                child: AppSearchBar(
                  key: const Key('destination_places_search_bar'),
                  controller: _searchCtrl,
                  hintText: 'Tìm địa điểm tại ${widget.destination.name}...',
                  onChanged: _onSearchChanged,
                  onSubmitted: (q) {
                    _debounce?.cancel();
                    _load(search: q);
                  },
                  onClear: () {
                    _searchCtrl.clear();
                    _onSearchChanged('');
                  },
                ),
              ),
              const Divider(height: 1),
              if (useScrollFallback) bodyWidget else Expanded(child: bodyWidget),
              if (!isKeyboardOpen)
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
            ];

            if (useScrollFallback) {
              return SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: columnChildren,
                ),
              );
            }

            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: columnChildren,
            );
          },
        ),
      ),
    );
  }
}
