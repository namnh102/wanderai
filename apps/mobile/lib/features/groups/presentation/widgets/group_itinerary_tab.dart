import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_badge.dart';
import '../../../../core/widgets/app_button.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/app_empty_state.dart';
import '../../../../core/widgets/app_error_state.dart';
import '../../../../core/widgets/app_loading.dart';
import '../../../../core/widgets/app_state_banner.dart';
import '../../../../core/widgets/app_text_field.dart';
import '../../../trips/data/trip_models.dart';
import '../../data/group_itinerary_models.dart';
import '../../providers/group_itinerary_provider.dart';

String _generateClientRequestId(String prefix) {
  final rng = Random();
  final hex = List.generate(
    16,
    (_) => rng.nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
  return '$prefix-${DateTime.now().microsecondsSinceEpoch}-$hex';
}

class GroupItineraryTabView extends ConsumerStatefulWidget {
  final String groupId;

  const GroupItineraryTabView({super.key, required this.groupId});

  @override
  ConsumerState<GroupItineraryTabView> createState() =>
      _GroupItineraryTabViewState();
}

class _GroupItineraryTabViewState extends ConsumerState<GroupItineraryTabView> {
  bool _isReordering = false;
  List<GroupItineraryDayModel> _draftDays = const [];

  @override
  void initState() {
    super.initState();
    Future.microtask(
      () =>
          ref.read(groupItineraryProvider.notifier).loadItinerary(widget.groupId),
    );
  }

  void _enterReorderMode(GroupItineraryStateModel model) {
    setState(() {
      _isReordering = true;
      _draftDays = model.days
          .map(
            (d) => d.copyWith(
              items: List<GroupItineraryItemModel>.from(d.items),
            ),
          )
          .toList();
    });
  }

  void _cancelReorderMode() {
    setState(() {
      _isReordering = false;
      _draftDays = const [];
    });
  }

  void _moveDraftItem(int dayNumber, int oldIndex, int newIndex) {
    setState(() {
      _draftDays = _draftDays.map((day) {
        if (day.dayNumber != dayNumber) return day;
        final mutable = List<GroupItineraryItemModel>.from(day.items);
        if (oldIndex < 0 ||
            oldIndex >= mutable.length ||
            newIndex < 0 ||
            newIndex >= mutable.length) {
          return day;
        }
        final moved = mutable.removeAt(oldIndex);
        mutable.insert(newIndex, moved);
        final reindexed = [
          for (var i = 0; i < mutable.length; i++)
            mutable[i].copyWith(orderIndex: i + 1),
        ];
        return day.copyWith(items: reindexed);
      }).toList();
    });
  }

  Future<void> _saveReorder() async {
    final entries = <ReorderItineraryItemEntry>[];
    for (final day in _draftDays) {
      for (var i = 0; i < day.items.length; i++) {
        entries.add(
          ReorderItineraryItemEntry(
            itemId: day.items[i].id,
            orderIndex: i + 1,
          ),
        );
      }
    }
    if (entries.isEmpty) {
      _cancelReorderMode();
      return;
    }
    final ok = await ref
        .read(groupItineraryProvider.notifier)
        .reorderItems(widget.groupId, ReorderItineraryRequest(items: entries));
    if (ok && mounted) {
      setState(() {
        _isReordering = false;
        _draftDays = const [];
      });
    }
  }

  Future<void> _openProposeDialog() async {
    final req = await showDialog<ProposeGroupItineraryItemRequest>(
      context: context,
      builder: (_) => const _ProposeItineraryDialog(),
    );
    if (req != null && mounted) {
      await ref
          .read(groupItineraryProvider.notifier)
          .proposeItem(widget.groupId, req);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(groupItineraryProvider);

    if (state.isLoading && state.itinerary == null) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: AppSpacing.xl),
        child: AppLoading(message: 'Đang tải lịch trình nhóm...'),
      );
    }

    if (state.errorMessage != null && state.itinerary == null) {
      if (state.isTripAccessForbidden) {
        return Padding(
          key: const Key('group_itinerary_trip_forbidden_state'),
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
          child: AppEmptyState(
            icon: Icons.lock_outline_rounded,
            title: 'Chưa có quyền truy cập lịch trình chuyến đi',
            description: state.errorMessage!,
          ),
        );
      }
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
        child: AppErrorState(
          key: const Key('group_itinerary_error_state'),
          title: state.isForbidden
              ? 'Không có quyền truy cập'
              : 'Không thể tải lịch trình nhóm',
          message: state.errorMessage!,
          onRetry: () => ref
              .read(groupItineraryProvider.notifier)
              .loadItinerary(widget.groupId),
        ),
      );
    }

    final model = state.itinerary;
    if (model == null) {
      return const SizedBox.shrink();
    }

    if (!model.tripLinked) {
      return Padding(
        key: const Key('group_itinerary_unlinked_state'),
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Row(
                children: [
                  Icon(
                    Icons.luggage_outlined,
                    color: AppColors.primary,
                  ),
                  SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Text(
                      'Nhóm chưa gắn chuyến đi hợp lệ',
                      style: AppTypography.h3,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                model.guidanceMessage ??
                    (model.canAttachTrip
                        ? 'Mở màn Chi tiết chuyến đi để tạo hoặc mở nhóm đồng hành gắn với chuyến đi trước khi đề xuất và bình chọn lịch trình.'
                        : 'Chờ chủ chuyến hoặc trưởng nhóm gắn chuyến đi hợp lệ trước khi đề xuất và bình chọn lịch trình.'),
                style: AppTypography.bodyM.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
              if (model.canAttachTrip) ...[
                const SizedBox(height: AppSpacing.md),
                AppButton(
                  key: const Key('group_itinerary_open_trips_button'),
                  text: 'Mở danh sách chuyến đi',
                  icon: Icons.arrow_forward_rounded,
                  variant: AppButtonVariant.secondary,
                  isFullWidth: false,
                  onPressed: () => context.go('/trips'),
                ),
              ],
            ],
          ),
        ),
      );
    }

    final isCancelled = model.tripStatus == 'CANCELLED';
    final hasReorderableDay = model.days.any((d) => d.items.length >= 2);
    final displayDays = _isReordering ? _draftDays : model.days;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (state.actionErrorMessage != null) ...[
          AppStateBanner(
            key: const Key('group_itinerary_action_error_banner'),
            tone: AppStateBannerTone.error,
            message: state.actionErrorMessage!,
            actionLabel: 'Đóng',
            onAction: () =>
                ref.read(groupItineraryProvider.notifier).clearActionError(),
          ),
          const SizedBox(height: AppSpacing.sm),
        ],
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            if (!isCancelled && !_isReordering)
              AppButton(
                key: const Key('group_itinerary_propose_button'),
                text: 'Đề xuất hoạt động',
                icon: Icons.add_location_alt_outlined,
                isFullWidth: false,
                isLoading: state.isMutating,
                onPressed: state.isMutating ? null : _openProposeDialog,
              ),
            if (model.canReorder && hasReorderableDay && !_isReordering)
              AppButton(
                key: const Key('group_itinerary_reorder_toggle'),
                text: 'Đổi thứ tự',
                icon: Icons.swap_vert_rounded,
                variant: AppButtonVariant.secondary,
                isFullWidth: false,
                onPressed:
                    state.isMutating ? null : () => _enterReorderMode(model),
              ),
          ],
        ),
        if (_isReordering) ...[
          const SizedBox(height: AppSpacing.sm),
          AppCard(
            key: const Key('group_itinerary_reorder_toolbar'),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                const Expanded(
                  child: Text(
                    'Chủ chuyến đang đổi thứ tự hoạt động trong ngày.',
                    style: AppTypography.bodyS,
                  ),
                ),
                TextButton(
                  key: const Key('group_itinerary_reorder_cancel'),
                  onPressed: state.isMutating ? null : _cancelReorderMode,
                  child: const Text('Hủy'),
                ),
                const SizedBox(width: AppSpacing.xs),
                AppButton(
                  key: const Key('group_itinerary_reorder_save'),
                  text: 'Lưu thứ tự',
                  icon: Icons.check_rounded,
                  isFullWidth: false,
                  isLoading: state.isMutating,
                  onPressed: state.isMutating ? null : _saveReorder,
                ),
              ],
            ),
          ),
        ],
        const SizedBox(height: AppSpacing.md),
        if (displayDays.isEmpty ||
            displayDays.every((day) => day.items.isEmpty))
          const AppEmptyState(
            key: Key('group_itinerary_empty_state'),
            icon: Icons.event_note_outlined,
            title: 'Chưa có hoạt động đề xuất',
            description:
                'Thành viên đủ quyền có thể đề xuất hoạt động mới để cả nhóm cùng bình chọn.',
          )
        else
          ...displayDays.map((day) {
            return Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    day.title != null && day.title!.trim().isNotEmpty
                        ? 'Ngày ${day.dayNumber}: ${day.title}'
                        : 'Ngày ${day.dayNumber}',
                    style: AppTypography.h3,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  for (var idx = 0; idx < day.items.length; idx++)
                    _buildItemCard(
                      day,
                      day.items[idx],
                      idx,
                      day.items.length,
                      state.isMutating,
                      isCancelled,
                    ),
                ],
              ),
            );
          }),
      ],
    );
  }

  Widget _buildItemCard(
    GroupItineraryDayModel day,
    GroupItineraryItemModel item,
    int index,
    int totalInDay,
    bool isMutating,
    bool isCancelled,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: AppCard(
        key: Key('group_itinerary_item_${item.id}'),
        padding: const EdgeInsets.all(AppSpacing.mdSmall),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  radius: 14,
                  backgroundColor: AppColors.primaryContainer,
                  child: Text(
                    '${item.orderIndex}',
                    style: AppTypography.label.copyWith(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.activity,
                        style: AppTypography.bodyM.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      if (item.placeName != null)
                        Text(
                          item.placeName!,
                          style: AppTypography.bodyS.copyWith(
                            color: AppColors.primary,
                          ),
                        ),
                      if (item.createdBy != null)
                        Text(
                          'Đề xuất bởi: ${item.createdBy!.displayName}',
                          style: AppTypography.bodyS.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                      if (item.notes != null && item.notes!.trim().isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 2),
                          child: Text(
                            item.notes!,
                            style: AppTypography.bodyS.copyWith(
                              color: AppColors.textSecondary,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
                if (_isReordering)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        key: Key('group_itinerary_move_up_${item.id}'),
                        tooltip: 'Đưa lên',
                        icon: const Icon(Icons.arrow_upward_rounded, size: 20),
                        onPressed: isMutating || index == 0
                            ? null
                            : () =>
                                _moveDraftItem(day.dayNumber, index, index - 1),
                      ),
                      IconButton(
                        key: Key('group_itinerary_move_down_${item.id}'),
                        tooltip: 'Đưa xuống',
                        icon: const Icon(
                          Icons.arrow_downward_rounded,
                          size: 20,
                        ),
                        onPressed: isMutating || index >= totalInDay - 1
                            ? null
                            : () =>
                                _moveDraftItem(day.dayNumber, index, index + 1),
                      ),
                    ],
                  )
                else if (item.canDelete)
                  IconButton(
                    key: Key('group_itinerary_delete_${item.id}'),
                    tooltip: 'Xóa hoạt động',
                    icon: const Icon(
                      Icons.delete_outline_rounded,
                      color: AppColors.error,
                    ),
                    onPressed: isMutating
                        ? null
                        : () => ref
                            .read(groupItineraryProvider.notifier)
                            .deleteItem(widget.groupId, item.id),
                  ),
              ],
            ),
            if (!_isReordering) ...[
              const SizedBox(height: AppSpacing.xs),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.xs,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  OutlinedButton.icon(
                    key: Key('group_itinerary_upvote_${item.id}'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: item.myVote == true
                          ? AppColors.primary
                          : AppColors.textSecondary,
                      backgroundColor: item.myVote == true
                          ? AppColors.primaryContainer
                          : null,
                      visualDensity: VisualDensity.compact,
                    ),
                    onPressed: isMutating || isCancelled
                        ? null
                        : () => ref
                            .read(groupItineraryProvider.notifier)
                            .toggleOrSetVote(widget.groupId, item, true),
                    icon: Icon(
                      item.myVote == true
                          ? Icons.thumb_up_alt
                          : Icons.thumb_up_alt_outlined,
                      size: 16,
                    ),
                    label: Text('Tán thành (${item.upvotes})'),
                  ),
                  OutlinedButton.icon(
                    key: Key('group_itinerary_downvote_${item.id}'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: item.myVote == false
                          ? AppColors.error
                          : AppColors.textSecondary,
                      backgroundColor: item.myVote == false
                          ? AppColors.errorContainer
                          : null,
                      visualDensity: VisualDensity.compact,
                    ),
                    onPressed: isMutating || isCancelled
                        ? null
                        : () => ref
                            .read(groupItineraryProvider.notifier)
                            .toggleOrSetVote(widget.groupId, item, false),
                    icon: Icon(
                      item.myVote == false
                          ? Icons.thumb_down_alt
                          : Icons.thumb_down_alt_outlined,
                      size: 16,
                    ),
                    label: Text('Phản đối (${item.downvotes})'),
                  ),
                  AppBadge(
                    key: Key('group_itinerary_score_${item.id}'),
                    label: 'Điểm: ${item.score >= 0 ? '+${item.score}' : item.score}',
                    color: item.score >= 0 ? AppColors.primary : AppColors.error,
                    backgroundColor: item.score >= 0
                        ? AppColors.primaryContainer
                        : AppColors.errorContainer,
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

class _ProposeItineraryDialog extends StatefulWidget {
  const _ProposeItineraryDialog();

  @override
  State<_ProposeItineraryDialog> createState() =>
      _ProposeItineraryDialogState();
}

class _ProposeItineraryDialogState extends State<_ProposeItineraryDialog> {
  final _formKey = GlobalKey<FormState>();
  final _dayCtrl = TextEditingController(text: '1');
  final _activityCtrl = TextEditingController();
  final _notesCtrl = TextEditingController();
  late final String _clientRequestId = _generateClientRequestId('itin');

  @override
  void dispose() {
    _dayCtrl.dispose();
    _activityCtrl.dispose();
    _notesCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Đề xuất hoạt động lịch trình'),
      content: SizedBox(
        width: 400,
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AppTextField(
                  key: const Key('group_itinerary_day_input'),
                  controller: _dayCtrl,
                  labelText: 'Ngày thứ (1..60) *',
                  keyboardType: TextInputType.number,
                  validator: (val) {
                    final parsed = int.tryParse(val?.trim() ?? '');
                    if (parsed == null || parsed < 1 || parsed > 60) {
                      return 'Ngày phải là số nguyên từ 1 đến 60';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: AppSpacing.sm),
                AppTextField(
                  key: const Key('group_itinerary_activity_input'),
                  controller: _activityCtrl,
                  labelText: 'Tên hoạt động *',
                  hintText: 'Ví dụ: Ngắm hoàng hôn Tháp Đồng Hồ',
                  validator: (val) {
                    final trimmed = val?.trim() ?? '';
                    if (trimmed.isEmpty) {
                      return 'Hoạt động không được để trống';
                    }
                    if (trimmed.length > 300) {
                      return 'Hoạt động tối đa 300 ký tự';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: AppSpacing.sm),
                AppTextField(
                  key: const Key('group_itinerary_notes_input'),
                  controller: _notesCtrl,
                  labelText: 'Ghi chú (tùy chọn)',
                  maxLines: 2,
                ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Hủy'),
        ),
        AppButton(
          key: const Key('group_itinerary_propose_submit'),
          text: 'Gửi đề xuất',
          isFullWidth: false,
          onPressed: () {
            if (!_formKey.currentState!.validate()) return;
            Navigator.of(context).pop(
              ProposeGroupItineraryItemRequest(
                dayNumber: int.parse(_dayCtrl.text.trim()),
                activity: _activityCtrl.text.trim(),
                notes: _notesCtrl.text.trim(),
                clientRequestId: _clientRequestId,
              ),
            );
          },
        ),
      ],
    );
  }
}
