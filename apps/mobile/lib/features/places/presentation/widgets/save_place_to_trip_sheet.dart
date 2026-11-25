import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/network/api_error.dart';
import '../../../../core/router/app_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_button.dart';
import '../../../../core/widgets/app_loading.dart';
import '../../../../core/widgets/app_state_banner.dart';
import '../../../../core/widgets/app_text_field.dart';
import '../../../../core/widgets/responsive_wrapper.dart';
import '../../../map/data/place_model.dart';
import '../../../trips/data/trip_models.dart';
import '../../../trips/providers/trip_provider.dart';

/// Opens a modal bottom sheet allowing the authenticated user to pick an
/// existing trip (or create one inline) and persist [place] into its itinerary
/// via `POST /trips/:id/itinerary`. Returns the saved [TripModel] on success.
Future<TripModel?> showSavePlaceToTripSheet(
  BuildContext context, {
  required PlaceModel place,
}) {
  return showModalBottomSheet<TripModel>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    backgroundColor: Colors.transparent,
    builder: (_) => _SavePlaceToTripSheet(place: place),
  );
}

class _SavePlaceToTripSheet extends ConsumerStatefulWidget {
  final PlaceModel place;

  const _SavePlaceToTripSheet({required this.place});

  @override
  ConsumerState<_SavePlaceToTripSheet> createState() =>
      _SavePlaceToTripSheetState();
}

class _SavePlaceToTripSheetState extends ConsumerState<_SavePlaceToTripSheet> {
  String? _selectedTripId;
  TripModel? _createdPendingTrip;
  String? _pendingClientRequestId;
  String? _pendingRequestScope;
  bool _createNewMode = false;
  int _selectedDay = 1;
  bool _saving = false;
  String? _errorText;
  AppStateBannerTone _errorTone = AppStateBannerTone.error;
  late final TextEditingController _newTitleCtrl;

  @override
  void initState() {
    super.initState();
    final destLabel = widget.place.destinationName?.trim();
    _newTitleCtrl = TextEditingController(
      text: (destLabel != null && destLabel.isNotEmpty)
          ? 'Khám phá $destLabel'
          : 'Chuyến đi khám phá mới',
    );
    Future.microtask(() async {
      if (!mounted) return;
      await ref.read(tripListProvider.notifier).loadTrips();
      if (!mounted) return;
      final tripState = ref.read(tripListProvider);
      if (tripState.errorMessage == null || tripState.trips.isNotEmpty) {
        _syncDefaultSelection(tripState.trips);
      }
    });
  }

  @override
  void dispose() {
    _newTitleCtrl.dispose();
    super.dispose();
  }

  void _syncDefaultSelection(List<TripModel> trips) {
    if (trips.isEmpty) {
      setState(() {
        _createNewMode = true;
        _selectedTripId = null;
      });
      return;
    }
    if (_selectedTripId != null && trips.any((t) => t.id == _selectedTripId)) {
      return;
    }
    final matching = trips.where((t) {
      if (widget.place.destinationId != null &&
          t.destinationId == widget.place.destinationId) {
        return true;
      }
      if (widget.place.destinationName != null &&
          t.destinationName != null &&
          t.destinationName!.toLowerCase() ==
              widget.place.destinationName!.toLowerCase()) {
        return true;
      }
      return false;
    });
    setState(() {
      _selectedTripId =
          matching.isNotEmpty ? matching.first.id : trips.first.id;
      _createNewMode = false;
    });
  }

  Future<void> _handleSave(List<TripModel> trips) async {
    setState(() {
      _saving = true;
      _errorText = null;
    });

    try {
      TripModel? targetTrip;
      if (_createNewMode || (trips.isEmpty && _createdPendingTrip == null)) {
        final rawTitle = _newTitleCtrl.text.trim();
        if (rawTitle.isEmpty) {
          setState(() {
            _saving = false;
            _errorTone = AppStateBannerTone.error;
            _errorText = 'Vui lòng nhập tên chuyến đi mới.';
          });
          return;
        }
        final createdTrip =
            await ref.read(tripListProvider.notifier).createTrip(
                  CreateTripRequest(
                    title: rawTitle,
                    destinationId: widget.place.destinationId,
                  ),
                );
        if (createdTrip == null) {
          if (!mounted) return;
          final tripState = ref.read(tripListProvider);
          setState(() {
            _saving = false;
            _errorTone = tripState.isOfflineError
                ? AppStateBannerTone.warning
                : AppStateBannerTone.error;
            _errorText =
                tripState.errorMessage ?? 'Không thể tạo chuyến đi mới.';
          });
          return;
        }
        if (!mounted) return;
        // Retain newly created trip.id immediately so any subsequent failure in
        // addItineraryItem will reuse this exact trip on retry instead of duplicating.
        setState(() {
          _createdPendingTrip = createdTrip;
          _selectedTripId = createdTrip.id;
          _createNewMode = false;
        });
        targetTrip = createdTrip;
      } else {
        targetTrip = trips
                .where((t) => t.id == _selectedTripId)
                .cast<TripModel?>()
                .firstWhere((t) => t != null, orElse: () => null) ??
            (_createdPendingTrip?.id == _selectedTripId
                ? _createdPendingTrip
                : null);
        if (targetTrip == null) {
          setState(() {
            _saving = false;
            _errorTone = AppStateBannerTone.error;
            _errorText = 'Vui lòng chọn một chuyến đi.';
          });
          return;
        }
      }

      final requestScope = '${targetTrip.id}:$_selectedDay:${widget.place.id}';
      if (_pendingClientRequestId == null ||
          _pendingRequestScope != requestScope) {
        _pendingRequestScope = requestScope;
        _pendingClientRequestId =
            'save-${DateTime.now().microsecondsSinceEpoch}-${widget.place.id}';
      }

      await ref.read(tripRepositoryProvider).addItineraryItem(
            targetTrip.id,
            AddItineraryItemRequest(
              dayNumber: _selectedDay,
              activity: 'Tham quan ${widget.place.name}',
              placeId: widget.place.id,
              notes: widget.place.hasAddress ? widget.place.address : null,
              clientRequestId: _pendingClientRequestId,
            ),
          );
      _pendingClientRequestId = null;
      _pendingRequestScope = null;

      if (kDebugMode) {
        debugPrint(
          '[GoMate][SaveToTrip] saved place_id=${widget.place.id} '
          'name="${widget.place.name}" -> trip_id=${targetTrip.id} '
          'title="${targetTrip.title}" day=$_selectedDay',
        );
      }

      // Guard post-save cache refreshes so a network blip after item creation
      // never causes a false error or duplicate itinerary item on retry.
      try {
        await ref.read(tripListProvider.notifier).loadTrips();
        if (ref.exists(tripDetailProvider) &&
            ref.read(tripDetailProvider).trip?.id == targetTrip.id) {
          await ref.read(tripDetailProvider.notifier).loadTrip(targetTrip.id);
        }
      } catch (_) {}

      if (!mounted) return;
      Navigator.of(context).pop(targetTrip);
    } on DioException catch (e) {
      if (!mounted) return;
      if (e.response?.statusCode == 401) {
        final redirect = '/places/${widget.place.id}';
        ref.read(postLoginRedirectProvider.notifier).state = redirect;
        Navigator.of(context).pop();
        context.go('/login?redirect=${Uri.encodeComponent(redirect)}');
        return;
      }
      final details = ApiErrorDetails.fromDioException(e);
      setState(() {
        _saving = false;
        if (details.isNetworkError) {
          _errorTone = AppStateBannerTone.warning;
          _errorText =
              'Mất kết nối mạng khi lưu. Chuyến đi đã chọn vẫn được giữ lại — hãy bấm Thử lại khi có mạng.';
        } else if (details.isTransientServerError) {
          _errorTone = AppStateBannerTone.warning;
          _errorText = details.message ??
              'Máy chủ tạm thời gián đoạn. Vui lòng bấm Thử lại.';
        } else {
          _errorTone = AppStateBannerTone.error;
          _errorText = details.message ??
              'Không thể lưu địa điểm vào chuyến đi lúc này.';
        }
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _errorTone = AppStateBannerTone.error;
        _errorText = 'Không thể lưu địa điểm vào chuyến đi lúc này.';
      });
    }
  }

  Widget _buildTripList(List<TripModel> trips) {
    final listView = ListView.separated(
      shrinkWrap: trips.length <= 4,
      physics: trips.length <= 4
          ? const NeverScrollableScrollPhysics()
          : const ClampingScrollPhysics(),
      itemCount: trips.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.xs),
      itemBuilder: (context, index) {
        final trip = trips[index];
        final isSelected = _selectedTripId == trip.id;
        return Material(
          color: isSelected
              ? AppColors.primaryContainer.withValues(alpha: 0.35)
              : AppColors.surface,
          shape: RoundedRectangleBorder(
            borderRadius: AppRadius.mdRadius,
            side: BorderSide(
              color: isSelected ? AppColors.primary : AppColors.softBorder,
              width: isSelected ? 1.5 : 1,
            ),
          ),
          clipBehavior: Clip.antiAlias,
          child: ListTile(
            key: Key('trip_picker_item_${trip.id}'),
            dense: true,
            onTap: _saving
                ? null
                : () => setState(() => _selectedTripId = trip.id),
            leading: Icon(
              isSelected
                  ? Icons.radio_button_checked
                  : Icons.radio_button_off,
              color: isSelected ? AppColors.primary : AppColors.textTertiary,
            ),
            title: Text(
              trip.title,
              style: AppTypography.label.copyWith(fontWeight: FontWeight.w700),
            ),
            subtitle: trip.destinationName != null
                ? Text(trip.destinationName!, style: AppTypography.bodyS)
                : null,
          ),
        );
      },
    );

    if (trips.length > 4) {
      return ConstrainedBox(
        constraints: const BoxConstraints(maxHeight: 260),
        child: listView,
      );
    }
    return listView;
  }

  @override
  Widget build(BuildContext context) {
    final tripState = ref.watch(tripListProvider);
    final trips = <TripModel>[
      if (_createdPendingTrip != null &&
          !tripState.trips.any((t) => t.id == _createdPendingTrip!.id))
        _createdPendingTrip!,
      ...tripState.trips,
    ];
    if (!tripState.isLoading &&
        trips.isNotEmpty &&
        !_createNewMode &&
        (_selectedTripId == null ||
            !trips.any((t) => t.id == _selectedTripId))) {
      _selectedTripId = trips.first.id;
    }

    final initialLoadFailed =
        tripState.errorMessage != null && trips.isEmpty && !tripState.isLoading;
    final maxHeight = MediaQuery.of(context).size.height * 0.82;

    return ResponsiveWrapper(
      maxWidth: 640.0,
      fillHeight: false,
      child: Container(
        key: const Key('save_place_to_trip_sheet'),
        constraints: BoxConstraints(maxHeight: maxHeight),
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
        ),
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
                AppSpacing.xs,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Lưu vào chuyến đi',
                          style: AppTypography.h3,
                        ),
                        const SizedBox(height: 2),
                        Text(
                          widget.place.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: AppTypography.bodyS.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Đóng',
                    icon: const Icon(Icons.close_rounded),
                    onPressed:
                        _saving ? null : () => Navigator.of(context).pop(),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: tripState.isLoading && trips.isEmpty
                    ? const Padding(
                        padding: EdgeInsets.symmetric(vertical: AppSpacing.lg),
                        child: AppLoading(
                          isCompact: true,
                          message: 'Đang tải danh sách chuyến đi...',
                        ),
                      )
                    : initialLoadFailed
                        ? AppStateBanner(
                            key: const Key('save_place_load_error_banner'),
                            message: tripState.errorMessage!,
                            tone: tripState.isOfflineError
                                ? AppStateBannerTone.warning
                                : AppStateBannerTone.error,
                            actionLabel: 'Thử lại',
                            onAction: () =>
                                ref.read(tripListProvider.notifier).loadTrips(),
                          )
                        : Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              if (trips.isNotEmpty) ...[
                                Wrap(
                                  spacing: AppSpacing.sm,
                                  runSpacing: AppSpacing.xs,
                                  alignment: WrapAlignment.spaceBetween,
                                  crossAxisAlignment: WrapCrossAlignment.center,
                                  children: [
                                    Text(
                                      _createNewMode
                                          ? 'Tạo chuyến đi mới'
                                          : 'Chọn chuyến đi của bạn',
                                      style: AppTypography.label.copyWith(
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    TextButton.icon(
                                      key: const Key(
                                        'trip_picker_new_trip_toggle',
                                      ),
                                      style: TextButton.styleFrom(
                                        minimumSize: Size.zero,
                                        tapTargetSize:
                                            MaterialTapTargetSize.shrinkWrap,
                                        padding: const EdgeInsets.symmetric(
                                          horizontal: 8,
                                          vertical: 6,
                                        ),
                                      ),
                                      onPressed: _saving
                                          ? null
                                          : () => setState(
                                                () => _createNewMode =
                                                    !_createNewMode,
                                              ),
                                      icon: Icon(
                                        _createNewMode
                                            ? Icons.list_alt_outlined
                                            : Icons.add_circle_outline,
                                        size: 16,
                                      ),
                                      label: Text(
                                        _createNewMode
                                            ? 'Chọn chuyến sẵn có'
                                            : 'Tạo chuyến mới',
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: AppSpacing.xs),
                              ],
                              if (_createNewMode || trips.isEmpty) ...[
                                if (trips.isEmpty)
                                  Padding(
                                    padding: const EdgeInsets.only(
                                      bottom: AppSpacing.sm,
                                    ),
                                    child: Text(
                                      'Bạn chưa có chuyến đi nào. Nhập tên chuyến đi bên dưới để tạo và lưu ngay địa điểm này.',
                                      style: AppTypography.bodyS.copyWith(
                                        color: AppColors.textSecondary,
                                      ),
                                    ),
                                  ),
                                AppTextField(
                                  key: const Key('trip_picker_new_title_input'),
                                  controller: _newTitleCtrl,
                                  enabled: !_saving,
                                  labelText: 'Tên chuyến đi mới',
                                  prefixIcon:
                                      const Icon(Icons.luggage_outlined),
                                ),
                              ] else
                                _buildTripList(trips),
                              const SizedBox(height: AppSpacing.md),
                              Wrap(
                                spacing: AppSpacing.sm,
                                crossAxisAlignment: WrapCrossAlignment.center,
                                children: [
                                  Text(
                                    'Thêm vào ngày:',
                                    style: AppTypography.label.copyWith(
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  DropdownButton<int>(
                                    key: const Key('trip_picker_day_dropdown'),
                                    value: _selectedDay,
                                    items: List.generate(
                                      14,
                                      (i) => DropdownMenuItem(
                                        value: i + 1,
                                        child: Text('Ngày ${i + 1}'),
                                      ),
                                    ),
                                    onChanged: _saving
                                        ? null
                                        : (val) {
                                            if (val != null) {
                                              setState(
                                                  () => _selectedDay = val);
                                            }
                                          },
                                  ),
                                ],
                              ),
                              if (_errorText != null) ...[
                                const SizedBox(height: AppSpacing.sm),
                                AppStateBanner(
                                  key: const Key('save_place_error_banner'),
                                  message: _errorText!,
                                  tone: _errorTone,
                                  actionLabel: 'Thử lại',
                                  onAction: _saving
                                      ? null
                                      : () => _handleSave(trips),
                                ),
                              ],
                            ],
                          ),
              ),
            ),
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.md,
                  AppSpacing.xs,
                  AppSpacing.md,
                  AppSpacing.md,
                ),
                child: AppButton(
                  key: const Key('trip_picker_confirm_save'),
                  text: _saving
                      ? 'Đang lưu...'
                      : (_createNewMode || trips.isEmpty
                          ? 'Tạo chuyến & Lưu'
                          : 'Lưu'),
                  icon: Icons.bookmark_added_outlined,
                  isLoading: _saving,
                  onPressed: (tripState.isLoading && trips.isEmpty) ||
                          initialLoadFailed ||
                          _saving
                      ? null
                      : () => _handleSave(trips),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
