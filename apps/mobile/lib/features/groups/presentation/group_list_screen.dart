import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_badge.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/app_empty_state.dart';
import '../../../core/widgets/app_error_state.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/app_state_banner.dart';
import '../../../core/widgets/app_text_field.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../data/group_models.dart';
import '../providers/group_provider.dart';

class GroupListScreen extends ConsumerStatefulWidget {
  final String? initialTripId;

  const GroupListScreen({super.key, this.initialTripId});

  @override
  ConsumerState<GroupListScreen> createState() => _GroupListScreenState();
}

class _GroupListScreenState extends ConsumerState<GroupListScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(
      () => ref.read(groupListProvider.notifier).loadGroups(),
    );
  }

  Future<void> _openCreateDialog() async {
    ref.read(groupListProvider.notifier).clearActionError();
    final created = await showDialog<GroupModel>(
      context: context,
      builder: (_) => _CreateGroupDialog(initialTripId: widget.initialTripId),
    );
    if (!mounted) return;
    if (created != null) {
      context.push('/groups/${created.id}');
    } else {
      ref.read(groupListProvider.notifier).clearActionError();
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(groupListProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Nhóm chuyến đi',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        actions: [
          IconButton(
            key: const Key('group_list_create_button'),
            icon: const Icon(Icons.group_add_outlined),
            tooltip: 'Tạo nhóm mới',
            onPressed: _openCreateDialog,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(groupListProvider.notifier).loadGroups(),
        child: ResponsiveWrapper(
          maxWidth: 720,
          child: _buildBody(context, state),
        ),
      ),
    );
  }

  Widget _buildBody(BuildContext context, GroupListState state) {
    if (state.isLoading && state.groups.isEmpty) {
      return const AppLoading(message: 'Đang tải danh sách nhóm...');
    }

    if (state.errorMessage != null && state.groups.isEmpty) {
      return AppErrorState(
        title: state.isOfflineError
            ? 'Không có kết nối mạng'
            : 'Không thể tải danh sách nhóm',
        message: state.errorMessage!,
        onRetry: () => ref.read(groupListProvider.notifier).loadGroups(),
      );
    }

    if (state.isEmpty) {
      return LayoutBuilder(
        builder: (context, constraints) => SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: constraints.maxHeight),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (state.actionErrorMessage != null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.md,
                      AppSpacing.md,
                      AppSpacing.md,
                      0,
                    ),
                    child: AppStateBanner(
                      tone: AppStateBannerTone.error,
                      message: state.actionErrorMessage!,
                      actionLabel: 'Đóng',
                      onAction: () => ref
                          .read(groupListProvider.notifier)
                          .clearActionError(),
                    ),
                  ),
                AppEmptyState(
                  icon: Icons.groups_outlined,
                  title: 'Chưa có nhóm chuyến đi nào',
                  description:
                      'Tạo nhóm đồng hành để quản lý thành viên và phối hợp lịch trình.',
                  actionLabel: 'Tạo nhóm mới',
                  onAction: _openCreateDialog,
                ),
              ],
            ),
          ),
        ),
      );
    }

    return ListView.builder(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: state.groups.length + (state.actionErrorMessage != null ? 1 : 0),
      itemBuilder: (context, index) {
        if (state.actionErrorMessage != null && index == 0) {
          return Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.md),
            child: AppStateBanner(
              tone: AppStateBannerTone.error,
              message: state.actionErrorMessage!,
              actionLabel: 'Đóng',
              onAction: () =>
                  ref.read(groupListProvider.notifier).clearActionError(),
            ),
          );
        }
        final groupIndex =
            state.actionErrorMessage != null ? index - 1 : index;
        final group = state.groups[groupIndex];
        return _buildGroupCard(context, group);
      },
    );
  }

  Widget _buildGroupCard(BuildContext context, GroupModel group) {
    final role = group.myRole ?? GroupRole.member;
    final isAdmin = role == GroupRole.admin;

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.mdSmall),
      child: AppCard(
        key: Key('group_card_${group.id}'),
        onTap: () => context.push('/groups/${group.id}'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    group.name,
                    style: AppTypography.h3,
                  ),
                ),
                const SizedBox(width: AppSpacing.sm),
                AppBadge(
                  label: role.label,
                  icon: isAdmin
                      ? Icons.workspace_premium_outlined
                      : Icons.person_outline,
                  color: isAdmin ? AppColors.primary : AppColors.info,
                  backgroundColor: isAdmin
                      ? AppColors.primaryContainer
                      : AppColors.infoContainer,
                ),
              ],
            ),
            if (group.description != null &&
                group.description!.trim().isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                group.description!,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: AppTypography.bodyS.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.md,
              runSpacing: AppSpacing.xs,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.people_outline,
                      size: 16,
                      color: AppColors.textSecondary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '${group.memberCount} thành viên',
                      style: AppTypography.bodyS.copyWith(
                        color: AppColors.textSecondary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
                if (group.tripTitle != null && group.tripTitle!.isNotEmpty)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.luggage_outlined,
                        size: 16,
                        color: AppColors.primary,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        group.tripTitle!,
                        style: AppTypography.bodyS.copyWith(
                          color: AppColors.primary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _CreateGroupDialog extends ConsumerStatefulWidget {
  final String? initialTripId;

  const _CreateGroupDialog({this.initialTripId});

  @override
  ConsumerState<_CreateGroupDialog> createState() => _CreateGroupDialogState();
}

class _CreateGroupDialogState extends ConsumerState<_CreateGroupDialog> {
  final _formKey = GlobalKey<FormState>();
  final _nameCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  late final TextEditingController _tripIdCtrl;

  @override
  void initState() {
    super.initState();
    _tripIdCtrl = TextEditingController(text: widget.initialTripId ?? '');
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    _tripIdCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final created = await ref.read(groupListProvider.notifier).createGroup(
          CreateGroupRequest(
            name: _nameCtrl.text,
            description: _descCtrl.text,
            tripId: _tripIdCtrl.text,
          ),
        );
    if (created != null && mounted) {
      Navigator.of(context).pop(created);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(groupListProvider);

    return AlertDialog(
      title: const Text('Tạo nhóm đồng hành'),
      content: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (widget.initialTripId != null &&
                  widget.initialTripId!.isNotEmpty) ...[
                const AppBadge(
                  label: 'Liên kết chuyến đi',
                  icon: Icons.link,
                  color: AppColors.primary,
                  backgroundColor: AppColors.primaryContainer,
                ),
                const SizedBox(height: AppSpacing.sm),
              ],
              AppTextField(
                key: const Key('group_create_name_input'),
                controller: _nameCtrl,
                labelText: 'Tên nhóm *',
                hintText: 'Ví dụ: Nhóm Hạ Long 2N1Đ',
                validator: (val) {
                  if (val == null || val.trim().isEmpty) {
                    return 'Vui lòng nhập tên nhóm';
                  }
                  if (val.trim().length > 120) {
                    return 'Tên nhóm tối đa 120 ký tự';
                  }
                  return null;
                },
              ),
              const SizedBox(height: AppSpacing.sm),
              AppTextField(
                key: const Key('group_create_desc_input'),
                controller: _descCtrl,
                labelText: 'Mô tả nhóm',
                hintText: 'Ghi chú ngắn về mục tiêu hoặc lịch trình nhóm',
                maxLines: 3,
              ),
              if (state.actionErrorMessage != null) ...[
                const SizedBox(height: AppSpacing.sm),
                Text(
                  state.actionErrorMessage!,
                  style: AppTypography.bodyS.copyWith(color: AppColors.error),
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          key: const Key('group_create_cancel_button'),
          onPressed: state.isCreating
              ? null
              : () {
                  ref.read(groupListProvider.notifier).clearActionError();
                  Navigator.of(context).pop();
                },
          child: const Text('Hủy'),
        ),
        AppButton(
          key: const Key('group_create_submit_button'),
          text: 'Tạo nhóm',
          isLoading: state.isCreating,
          isFullWidth: false,
          onPressed: state.isCreating ? null : _submit,
        ),
      ],
    );
  }
}
