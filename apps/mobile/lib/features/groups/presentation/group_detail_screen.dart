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
import '../../profile/providers/profile_provider.dart';
import '../data/group_models.dart';
import '../providers/group_expense_provider.dart';
import '../providers/group_itinerary_provider.dart';
import '../providers/group_provider.dart';
import 'widgets/group_expense_tab.dart';
import 'widgets/group_itinerary_tab.dart';

class GroupDetailScreen extends ConsumerStatefulWidget {
  final String groupId;

  const GroupDetailScreen({super.key, required this.groupId});

  @override
  ConsumerState<GroupDetailScreen> createState() => _GroupDetailScreenState();
}

class _GroupDetailScreenState extends ConsumerState<GroupDetailScreen> {
  int _selectedSection = 0; // 0 = Thành viên, 1 = Lịch trình, 2 = Chi phí
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (!mounted) return;
      if (ref.read(profileProvider).user == null) {
        ref.read(profileProvider.notifier).loadProfile();
      }
      ref.read(groupDetailProvider.notifier).loadGroup(widget.groupId);
    });
  }

  Future<void> _openEditDialog(GroupModel group) async {
    final result = await showDialog<({String name, String description})>(
      context: context,
      builder: (_) => _EditGroupDialog(group: group),
    );

    if (result != null && mounted) {
      await ref.read(groupDetailProvider.notifier).updateGroup(
            group.id,
            UpdateGroupRequest(
              name: result.name,
              description: result.description,
            ),
          );
    }
  }

  Future<void> _openAddMemberDialog(GroupModel group) async {
    final targetUserId = await showDialog<String>(
      context: context,
      builder: (_) => const _AddMemberDialog(),
    );

    if (targetUserId != null && mounted) {
      await ref
          .read(groupDetailProvider.notifier)
          .addMember(group.id, targetUserId);
    }
  }

  Future<void> _confirmRemoveMember(
    GroupModel group,
    GroupMemberModel member,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Xóa thành viên khỏi nhóm'),
        content: Text(
          'Bạn có chắc muốn xóa "${member.user.displayName}" khỏi nhóm "${group.name}"?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Hủy'),
          ),
          AppButton(
            key: const Key('group_remove_member_confirm_button'),
            text: 'Xóa',
            variant: AppButtonVariant.danger,
            isFullWidth: false,
            onPressed: () => Navigator.of(dialogContext).pop(true),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      await ref
          .read(groupDetailProvider.notifier)
          .removeMember(group.id, member.userId);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(groupDetailProvider);
    final currentUserId = ref.watch(profileProvider.select((s) => s.user?.id));

    return Scaffold(
      appBar: AppBar(
        title: Text(
          state.group?.name ?? 'Chi tiết nhóm',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
      body: ResponsiveWrapper(
        maxWidth: 720,
        child: _buildBody(context, state, currentUserId),
      ),
    );
  }

  Widget _buildBody(
    BuildContext context,
    GroupDetailState state,
    String? currentUserId,
  ) {
    if (state.isLoading && state.group == null) {
      return const AppLoading(message: 'Đang tải thông tin nhóm...');
    }

    if (state.group == null && state.errorMessage != null) {
      if (state.isForbidden) {
        return Center(
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AppErrorState(
                  key: const Key('group_detail_forbidden_state'),
                  title: 'Truy cập bị từ chối (403)',
                  message: state.errorMessage!,
                  onRetry: () => ref
                      .read(groupDetailProvider.notifier)
                      .loadGroup(widget.groupId),
                ),
                AppButton(
                  text: 'Quay lại danh sách nhóm',
                  variant: AppButtonVariant.tonal,
                  isFullWidth: false,
                  onPressed: () => context.go('/groups'),
                ),
              ],
            ),
          ),
        );
      }

      return AppErrorState(
        title: state.isNotFound
            ? 'Không tìm thấy nhóm'
            : (state.isOfflineError
                ? 'Không có kết nối mạng'
                : 'Không thể tải nhóm'),
        message: state.errorMessage!,
        onRetry: () =>
            ref.read(groupDetailProvider.notifier).loadGroup(widget.groupId),
      );
    }

    final group = state.group;
    if (group == null) {
      return const AppLoading(message: 'Đang tải thông tin nhóm...');
    }

    final resolvedRole = group.resolveMyRole(currentUserId) ?? GroupRole.member;
    final isAdmin = group.canManage(currentUserId);

    return RefreshIndicator(
      onRefresh: () async {
        await ref.read(groupDetailProvider.notifier).loadGroup(widget.groupId);
        if (_selectedSection == 1) {
          await ref
              .read(groupItineraryProvider.notifier)
              .loadItinerary(widget.groupId);
        } else if (_selectedSection == 2) {
          await ref
              .read(groupExpenseProvider.notifier)
              .loadLedger(widget.groupId);
        }
      },
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          if (state.actionErrorMessage != null) ...[
            AppStateBanner(
              key: const Key('group_detail_action_error_banner'),
              tone: AppStateBannerTone.error,
              message: state.actionErrorMessage!,
              actionLabel: 'Đóng',
              onAction: () =>
                  ref.read(groupDetailProvider.notifier).clearActionError(),
            ),
            const SizedBox(height: AppSpacing.md),
          ],

          // Header Card
          AppCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        group.name,
                        style: AppTypography.h2,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    AppBadge(
                      key: const Key('group_detail_my_role_badge'),
                      label: resolvedRole.label,
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
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    group.description!,
                    style: AppTypography.bodyM.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
                const SizedBox(height: AppSpacing.mdSmall),
                Wrap(
                  spacing: AppSpacing.md,
                  runSpacing: AppSpacing.xs,
                  children: [
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.people_outline,
                          size: 18,
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
                            size: 18,
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
          const SizedBox(height: AppSpacing.md),

          SegmentedButton<int>(
            key: const Key('group_detail_section_switcher'),
            segments: const [
              ButtonSegment<int>(
                value: 0,
                icon: Icon(Icons.group_outlined, size: 18),
                label: Text('Thành viên'),
              ),
              ButtonSegment<int>(
                value: 1,
                icon: Icon(Icons.how_to_vote_outlined, size: 18),
                label: Text('Lịch trình'),
              ),
              ButtonSegment<int>(
                value: 2,
                icon: Icon(Icons.payments_outlined, size: 18),
                label: Text('Chi phí'),
              ),
            ],
            selected: {_selectedSection},
            onSelectionChanged: (selection) {
              setState(() {
                _selectedSection = selection.first;
              });
            },
          ),
          const SizedBox(height: AppSpacing.md),

          if (_selectedSection == 1)
            GroupItineraryTabView(groupId: group.id)
          else if (_selectedSection == 2)
            GroupExpenseTabView(
              group: group,
              currentUserId: currentUserId,
              isAdmin: isAdmin,
            )
          else ...[
          // Permission & Privileged Actions Bar
          if (isAdmin)
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                AppButton(
                  key: const Key('group_edit_button'),
                  text: 'Chỉnh sửa nhóm',
                  icon: Icons.edit_outlined,
                  variant: AppButtonVariant.secondary,
                  isFullWidth: false,
                  isLoading: state.isMutating,
                  onPressed:
                      state.isMutating ? null : () => _openEditDialog(group),
                ),
                AppButton(
                  key: const Key('group_add_member_button'),
                  text: 'Thêm thành viên',
                  icon: Icons.person_add_outlined,
                  isFullWidth: false,
                  isLoading: state.isMutating,
                  onPressed: state.isMutating
                      ? null
                      : () => _openAddMemberDialog(group),
                ),
              ],
            )
          else
            const AppStateBanner(
              key: Key('group_member_readonly_banner'),
              tone: AppStateBannerTone.info,
              message:
                  'Bạn đang ở vai trò Thành viên (member). Chỉ Trưởng nhóm (admin) mới có quyền chỉnh sửa nhóm hoặc quản lý thành viên.',
            ),

          const SizedBox(height: AppSpacing.lg),
          Text(
            'Thành viên nhóm (${group.members.length})',
            style: AppTypography.h3,
          ),
          const SizedBox(height: AppSpacing.sm),

          if (group.members.isEmpty)
            const AppEmptyState(
              key: Key('group_members_empty_state'),
              icon: Icons.group_off_outlined,
              title: 'Chưa có thành viên',
              description: 'Nhóm hiện chưa có thành viên nào.',
            )
          else
            ...group.members.map((member) {
              final isSelf =
                  currentUserId != null && member.userId == currentUserId;
              final removable = isAdmin &&
                  !member.isTripOwner &&
                  (!member.isAdmin || group.adminCount > 1);
              final initial = member.user.displayName.isNotEmpty
                  ? member.user.displayName[0].toUpperCase()
                  : 'G';

              return Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: AppCard(
                  key: Key('group_member_row_${member.userId}'),
                  padding: const EdgeInsets.all(AppSpacing.mdSmall),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      CircleAvatar(
                        radius: 20,
                        backgroundColor: member.isAdmin
                            ? AppColors.primaryContainer
                            : AppColors.infoContainer,
                        child: Text(
                          initial,
                          style: AppTypography.h3.copyWith(
                            color: member.isAdmin
                                ? AppColors.primary
                                : AppColors.info,
                          ),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.mdSmall),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Wrap(
                              spacing: AppSpacing.sm,
                              runSpacing: AppSpacing.xs,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                Text(
                                  isSelf
                                      ? '${member.user.displayName} (Bạn)'
                                      : member.user.displayName,
                                  style: AppTypography.bodyM.copyWith(
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                                AppBadge(
                                  key: Key(
                                    'group_member_role_badge_${member.userId}',
                                  ),
                                  label: member.role.label,
                                  color: member.isAdmin
                                      ? AppColors.primary
                                      : AppColors.info,
                                  backgroundColor: member.isAdmin
                                      ? AppColors.primaryContainer
                                      : AppColors.infoContainer,
                                ),
                              ],
                            ),
                            if (member.user.bio != null &&
                                member.user.bio!.trim().isNotEmpty) ...[
                              const SizedBox(height: 4),
                              Text(
                                member.user.bio!,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: AppTypography.bodyS.copyWith(
                                  color: AppColors.textSecondary,
                                ),
                              ),
                            ],
                          ],
                        ),
                      ),
                      if (removable)
                        IconButton(
                          key: Key(
                            'group_remove_member_btn_${member.userId}',
                          ),
                          icon: const Icon(
                            Icons.person_remove_outlined,
                            color: AppColors.error,
                          ),
                          tooltip: 'Xóa thành viên',
                          onPressed: state.isMutating
                              ? null
                              : () => _confirmRemoveMember(group, member),
                        ),
                    ],
                  ),
                ),
              );
            }),
          ],
        ],
      ),
    );
  }
}

class _EditGroupDialog extends StatefulWidget {
  final GroupModel group;

  const _EditGroupDialog({required this.group});

  @override
  State<_EditGroupDialog> createState() => _EditGroupDialogState();
}

class _EditGroupDialogState extends State<_EditGroupDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameCtrl;
  late final TextEditingController _descCtrl;

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(text: widget.group.name);
    _descCtrl = TextEditingController(text: widget.group.description ?? '');
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _descCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Chỉnh sửa thông tin nhóm'),
      content: SizedBox(
        width: 400,
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AppTextField(
                  key: const Key('group_edit_name_input'),
                  controller: _nameCtrl,
                  labelText: 'Tên nhóm *',
                  validator: (val) {
                    if (val == null || val.trim().isEmpty) {
                      return 'Tên nhóm không được để trống';
                    }
                    if (val.trim().length > 120) {
                      return 'Tên nhóm tối đa 120 ký tự';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: AppSpacing.sm),
                AppTextField(
                  key: const Key('group_edit_desc_input'),
                  controller: _descCtrl,
                  labelText: 'Mô tả nhóm',
                  maxLines: 3,
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
          key: const Key('group_edit_submit_button'),
          text: 'Lưu thay đổi',
          isFullWidth: false,
          onPressed: () {
            if (!_formKey.currentState!.validate()) return;
            Navigator.of(context).pop((
              name: _nameCtrl.text,
              description: _descCtrl.text,
            ));
          },
        ),
      ],
    );
  }
}

class _AddMemberDialog extends StatefulWidget {
  const _AddMemberDialog();

  @override
  State<_AddMemberDialog> createState() => _AddMemberDialogState();
}

class _AddMemberDialogState extends State<_AddMemberDialog> {
  final _formKey = GlobalKey<FormState>();
  final _userIdCtrl = TextEditingController();
  static final _uuidRegex = RegExp(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
  );

  @override
  void dispose() {
    _userIdCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Thêm thành viên'),
      content: SizedBox(
        width: 400,
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: AppTextField(
              key: const Key('group_add_member_userid_input'),
              controller: _userIdCtrl,
              labelText: 'UUID người dùng *',
              hintText: 'Nhập UUID tài khoản thành viên',
              validator: (val) {
                final trimmed = val?.trim() ?? '';
                if (trimmed.isEmpty) {
                  return 'Vui lòng nhập userId';
                }
                if (!_uuidRegex.hasMatch(trimmed)) {
                  return 'userId phải là UUID hợp lệ';
                }
                return null;
              },
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
          key: const Key('group_add_member_submit_button'),
          text: 'Thêm',
          isFullWidth: false,
          onPressed: () {
            if (!_formKey.currentState!.validate()) return;
            Navigator.of(context).pop(_userIdCtrl.text.trim());
          },
        ),
      ],
    );
  }
}
