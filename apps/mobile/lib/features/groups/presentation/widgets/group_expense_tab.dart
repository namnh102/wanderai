import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
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
import '../../data/group_expense_models.dart';
import '../../data/group_models.dart';
import '../../providers/group_expense_provider.dart';

String _newClientReqId(String prefix) {
  final rng = Random();
  final hex = List.generate(
    16,
    (_) => rng.nextInt(256).toRadixString(16).padLeft(2, '0'),
  ).join();
  return '$prefix-${DateTime.now().microsecondsSinceEpoch}-$hex';
}

class GroupExpenseTabView extends ConsumerStatefulWidget {
  final GroupModel group;
  final String? currentUserId;
  final bool isAdmin;

  const GroupExpenseTabView({
    super.key,
    required this.group,
    required this.currentUserId,
    required this.isAdmin,
  });

  @override
  ConsumerState<GroupExpenseTabView> createState() =>
      _GroupExpenseTabViewState();
}

class _GroupExpenseTabViewState extends ConsumerState<GroupExpenseTabView> {
  final Map<String, String> _settlementReqIds = {};

  @override
  void initState() {
    super.initState();
    Future.microtask(
      () => ref.read(groupExpenseProvider.notifier).loadLedger(widget.group.id),
    );
  }

  String _getOrCreateSettlementKey(SuggestedSettlementModel s) {
    final slot = '${s.fromUserId}:${s.toUserId}:${s.amount}';
    return _settlementReqIds.putIfAbsent(
      slot,
      () => _newClientReqId('settle'),
    );
  }

  Future<void> _openCreateExpenseDialog() async {
    final req = await showDialog<CreateExpenseRequest>(
      context: context,
      builder: (_) => _CreateExpenseDialog(
        group: widget.group,
        currentUserId: widget.currentUserId,
      ),
    );
    if (req != null && mounted) {
      await ref
          .read(groupExpenseProvider.notifier)
          .createExpense(widget.group.id, req);
    }
  }

  Future<void> _confirmSuggestedSettlement(SuggestedSettlementModel s) async {
    final reqId = _getOrCreateSettlementKey(s);
    final ok = await ref
        .read(groupExpenseProvider.notifier)
        .confirmSettlement(
          widget.group.id,
          CreateSettlementRequest(
            debtorId: s.fromUserId,
            creditorId: s.toUserId,
            amount: s.amount,
            clientRequestId: reqId,
          ),
        );
    if (ok) {
      _settlementReqIds.remove('${s.fromUserId}:${s.toUserId}:${s.amount}');
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(groupExpenseProvider);

    if (state.isLoading &&
        state.expenseList == null &&
        state.settlementPlan == null) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: AppSpacing.xl),
        child: AppLoading(message: 'Đang tải sổ chi phí nhóm...'),
      );
    }

    if (state.errorMessage != null && state.expenseList == null) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
        child: AppErrorState(
          key: const Key('group_expense_error_state'),
          title: 'Không thể tải sổ chi phí',
          message: state.errorMessage!,
          onRetry: () => ref
              .read(groupExpenseProvider.notifier)
              .loadLedger(widget.group.id),
        ),
      );
    }

    final expenseList = state.expenseList;
    final plan = state.settlementPlan;
    if (expenseList == null || plan == null) {
      return const SizedBox.shrink();
    }

    final normCurrent = widget.currentUserId?.trim().toLowerCase();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (state.actionErrorMessage != null) ...[
          AppStateBanner(
            key: const Key('group_expense_action_error_banner'),
            tone: AppStateBannerTone.error,
            message: state.actionErrorMessage!,
            actionLabel: 'Đóng',
            onAction: () =>
                ref.read(groupExpenseProvider.notifier).clearActionError(),
          ),
          const SizedBox(height: AppSpacing.sm),
        ],

        // Summary Card
        AppCard(
          key: const Key('group_expense_summary_card'),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Tổng chi tiêu nhóm',
                          style: AppTypography.bodyS.copyWith(
                            color: AppColors.textSecondary,
                          ),
                        ),
                        Text(
                          formatVnd(expenseList.totalSpent),
                          key: const Key('group_expense_total_spent_text'),
                          style: AppTypography.h2.copyWith(
                            color: AppColors.primary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        'Dư nợ cần đối soát',
                        style: AppTypography.bodyS.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                      Text(
                        formatVnd(plan.totalOutstandingDebt),
                        key: const Key('group_expense_outstanding_debt_text'),
                        style: AppTypography.h3.copyWith(
                          color: plan.totalOutstandingDebt > 0
                              ? AppColors.warning
                              : AppColors.primary,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: AppSpacing.mdSmall),
              AppButton(
                key: const Key('group_expense_add_button'),
                text: 'Thêm khoản chi (VND)',
                icon: Icons.add_card_outlined,
                isFullWidth: false,
                isLoading: state.isSubmitting,
                onPressed: state.isSubmitting ? null : _openCreateExpenseDialog,
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),

        // Member Balances
        if (plan.balances.isNotEmpty) ...[
          const Text('Số dư công nợ từng thành viên', style: AppTypography.h3),
          const SizedBox(height: AppSpacing.xs),
          ...plan.balances.map((b) {
            final isPos = b.netBalance > 0;
            final isNeg = b.netBalance < 0;
            final color = isPos
                ? AppColors.primary
                : (isNeg ? AppColors.error : AppColors.textSecondary);
            final prefix = isPos ? '+' : '';
            return Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: AppCard(
                key: Key('group_balance_row_${b.userId}'),
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.mdSmall,
                  vertical: AppSpacing.xs,
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        b.isActiveMember
                            ? b.user.displayName
                            : '${b.user.displayName} (Không hoạt động)',
                        style: AppTypography.bodyM.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    Text(
                      '$prefix${formatVnd(b.netBalance)}',
                      style: AppTypography.bodyM.copyWith(
                        color: color,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
          const SizedBox(height: AppSpacing.md),
        ],

        // Greedy Suggestions
        if (plan.suggestedTransactions.isNotEmpty) ...[
          const Text(
            'Gợi ý giảm lượt chuyển trả',
            style: AppTypography.h3,
          ),
          const SizedBox(height: AppSpacing.xs),
          ...plan.suggestedTransactions.asMap().entries.map((entry) {
            final idx = entry.key;
            final s = entry.value;
            final debtorNorm = s.fromUserId.trim().toLowerCase();
            final creditorNorm = s.toUserId.trim().toLowerCase();

            // Strict Owner Rule: Debtor can NEVER self-confirm, even if Admin!
            final isCurrentDebtor =
                normCurrent != null && normCurrent == debtorNorm;
            final canConfirm = normCurrent != null &&
                !isCurrentDebtor &&
                (normCurrent == creditorNorm || widget.isAdmin);

            return Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: AppCard(
                key: Key('group_suggestion_row_$idx'),
                padding: const EdgeInsets.all(AppSpacing.mdSmall),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${s.fromUser.displayName} chuyển cho ${s.toUser.displayName}',
                      style: AppTypography.bodyM.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      formatVnd(s.amount),
                      style: AppTypography.h3.copyWith(color: AppColors.primary),
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    if (canConfirm)
                      AppButton(
                        key: Key(
                          'group_confirm_settlement_${s.fromUserId}_${s.toUserId}',
                        ),
                        text: 'Xác nhận đã nhận',
                        icon: Icons.check_circle_outline_rounded,
                        isFullWidth: false,
                        isLoading: state.isSubmitting,
                        onPressed: state.isSubmitting
                            ? null
                            : () => _confirmSuggestedSettlement(s),
                      )
                    else
                      AppBadge(
                        key: Key(
                          'group_awaiting_creditor_badge_${s.fromUserId}_${s.toUserId}',
                        ),
                        label: isCurrentDebtor
                            ? 'Người nợ không tự xác nhận — chờ người nhận hoặc admin khác chốt'
                            : 'Chờ người nhận hoặc admin khác người nợ xác nhận',
                        color: AppColors.info,
                        backgroundColor: AppColors.infoContainer,
                      ),
                  ],
                ),
              ),
            );
          }),
          const SizedBox(height: AppSpacing.md),
        ],

        if (expenseList.hasSettlements) ...[
          const AppStateBanner(
            key: Key('group_expense_locked_banner'),
            tone: AppStateBannerTone.info,
            message:
                'Nhóm đã có bản ghi đối soát nên các khoản chi cũ đã được khóa xóa để bảo toàn sổ cái.',
          ),
          const SizedBox(height: AppSpacing.sm),
        ],

        const Text('Lịch sử khoản chi', style: AppTypography.h3),
        const SizedBox(height: AppSpacing.xs),
        if (expenseList.expenses.isEmpty)
          const AppEmptyState(
            key: Key('group_expense_empty_state'),
            icon: Icons.receipt_long_outlined,
            title: 'Chưa có khoản chi nào',
            description:
                'Thêm khoản chi bằng số nguyên VND để chia đều hoặc chia tùy chỉnh cho các thành viên.',
          )
        else
          ...expenseList.expenses.map((exp) {
            return Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: AppCard(
                key: Key('group_expense_item_${exp.id}'),
                padding: const EdgeInsets.all(AppSpacing.mdSmall),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                exp.title,
                                style: AppTypography.bodyM.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              Text(
                                '${formatVnd(exp.amount)} • Trả bởi ${exp.paidBy?.displayName ?? exp.paidByUserId} (${exp.splitType.label})',
                                style: AppTypography.bodyS.copyWith(
                                  color: AppColors.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                        if (exp.canDelete)
                          IconButton(
                            key: Key('group_expense_delete_${exp.id}'),
                            tooltip: 'Xóa khoản chi',
                            icon: const Icon(
                              Icons.delete_outline_rounded,
                              color: AppColors.error,
                            ),
                            onPressed: state.isSubmitting
                                ? null
                                : () => ref
                                    .read(groupExpenseProvider.notifier)
                                    .deleteExpense(widget.group.id, exp.id),
                          ),
                      ],
                    ),
                    if (exp.splits.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Wrap(
                        spacing: AppSpacing.xs,
                        runSpacing: 4,
                        children: exp.splits.map((sp) {
                          return Chip(
                            visualDensity: VisualDensity.compact,
                            label: Text(
                              '${sp.user?.displayName ?? sp.userId}: ${formatVnd(sp.shareAmount)}',
                              style: AppTypography.bodyS,
                            ),
                          );
                        }).toList(),
                      ),
                    ],
                  ],
                ),
              ),
            );
          }),

        if (plan.settlements.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          const Text('Lịch sử đối soát hoàn trả', style: AppTypography.h3),
          const SizedBox(height: AppSpacing.xs),
          ...plan.settlements.map((st) {
            return Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: AppCard(
                key: Key('group_settlement_history_${st.id}'),
                padding: const EdgeInsets.all(AppSpacing.sm),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        '${st.debtor.displayName} → ${st.creditor.displayName}',
                        style: AppTypography.bodyS.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                    Text(
                      formatVnd(st.amount),
                      style: AppTypography.bodyS.copyWith(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            );
          }),
        ],
      ],
    );
  }
}

class _CreateExpenseDialog extends StatefulWidget {
  final GroupModel group;
  final String? currentUserId;

  const _CreateExpenseDialog({
    required this.group,
    required this.currentUserId,
  });

  @override
  State<_CreateExpenseDialog> createState() => _CreateExpenseDialogState();
}

class _CreateExpenseDialogState extends State<_CreateExpenseDialog> {
  final _formKey = GlobalKey<FormState>();
  final _titleCtrl = TextEditingController();
  final _amountCtrl = TextEditingController();
  SplitType _splitType = SplitType.equal;
  late String _paidByUserId;
  late final Map<String, TextEditingController> _customCtrls;
  late final String _clientRequestId = _newClientReqId('exp');
  String? _customError;

  @override
  void initState() {
    super.initState();
    final members = widget.group.members;
    _paidByUserId =
        (widget.currentUserId != null &&
                members.any((m) => m.userId == widget.currentUserId))
            ? widget.currentUserId!
            : (members.isNotEmpty ? members.first.userId : '');
    _customCtrls = {
      for (final m in members) m.userId: TextEditingController(text: '0'),
    };
  }

  @override
  void dispose() {
    _titleCtrl.dispose();
    _amountCtrl.dispose();
    for (final c in _customCtrls.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _submit() {
    setState(() => _customError = null);
    if (!_formKey.currentState!.validate()) return;
    final amount = int.parse(_amountCtrl.text.trim());
    final memberIds = widget.group.members.map((m) => m.userId).toList();

    if (_splitType == SplitType.equal) {
      if (amount < memberIds.length) {
        setState(() {
          _customError =
              'Số tiền chia đều phải >= ${memberIds.length} VND (số thành viên)';
        });
        return;
      }
      Navigator.of(context).pop(
        CreateExpenseRequest(
          title: _titleCtrl.text.trim(),
          amount: amount,
          paidByUserId: _paidByUserId,
          splitType: SplitType.equal,
          participantIds: memberIds,
          clientRequestId: _clientRequestId,
        ),
      );
      return;
    }

    final customEntries = <CustomSplitRequestEntry>[];
    var sum = 0;
    for (final m in widget.group.members) {
      final raw = _customCtrls[m.userId]?.text.trim() ?? '0';
      final val = int.tryParse(raw.isEmpty ? '0' : raw);
      if (val == null || val < 0) {
        setState(() {
          _customError =
              'Phần chia của ${m.user.displayName} phải là số nguyên VND >= 0';
        });
        return;
      }
      sum += val;
      if (val > 0) {
        customEntries.add(
          CustomSplitRequestEntry(userId: m.userId, shareAmount: val),
        );
      }
    }

    if (sum != amount || customEntries.isEmpty) {
      setState(() {
        _customError =
            'Tổng phần chia (${formatVnd(sum)}) phải khớp đúng ${formatVnd(amount)}';
      });
      return;
    }

    Navigator.of(context).pop(
      CreateExpenseRequest(
        title: _titleCtrl.text.trim(),
        amount: amount,
        paidByUserId: _paidByUserId,
        splitType: SplitType.custom,
        customSplits: customEntries,
        clientRequestId: _clientRequestId,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final parsedAmount = int.tryParse(_amountCtrl.text.trim()) ?? 0;
    final equalPreview = _splitType == SplitType.equal && parsedAmount > 0
        ? previewEqualSplits(
            parsedAmount,
            widget.group.members.map((m) => m.userId).toList(),
          )
        : const <({String userId, int shareAmount})>[];

    return AlertDialog(
      title: const Text('Thêm khoản chi nhóm (VND)'),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                AppTextField(
                  key: const Key('group_expense_title_input'),
                  controller: _titleCtrl,
                  labelText: 'Nội dung khoản chi *',
                  validator: (v) {
                    final t = v?.trim() ?? '';
                    if (t.isEmpty) return 'Không được để trống';
                    if (t.length > 200) return 'Tối đa 200 ký tự';
                    return null;
                  },
                ),
                const SizedBox(height: AppSpacing.sm),
                AppTextField(
                  key: const Key('group_expense_amount_input'),
                  controller: _amountCtrl,
                  labelText: 'Số tiền nguyên VND *',
                  keyboardType: TextInputType.number,
                  onChanged: (_) => setState(() {}),
                  validator: (v) {
                    final parsed = int.tryParse(v?.trim() ?? '');
                    if (parsed == null || parsed <= 0 || parsed > 2147483647) {
                      return 'Nhập số nguyên VND hợp lệ (> 0)';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: AppSpacing.sm),
                DropdownButtonFormField<String>(
                  key: const Key('group_expense_payer_dropdown'),
                  initialValue: _paidByUserId.isNotEmpty ? _paidByUserId : null,
                  decoration: const InputDecoration(
                    labelText: 'Người thanh toán hóa đơn',
                    border: OutlineInputBorder(),
                  ),
                  items: widget.group.members
                      .map(
                        (m) => DropdownMenuItem<String>(
                          value: m.userId,
                          child: Text(m.user.displayName),
                        ),
                      )
                      .toList(),
                  onChanged: (val) {
                    if (val != null) setState(() => _paidByUserId = val);
                  },
                ),
                const SizedBox(height: AppSpacing.sm),
                SegmentedButton<SplitType>(
                  key: const Key('group_expense_split_type_selector'),
                  segments: const [
                    ButtonSegment(
                      value: SplitType.equal,
                      label: Text('Chia đều'),
                    ),
                    ButtonSegment(
                      value: SplitType.custom,
                      label: Text('Tùy chỉnh'),
                    ),
                  ],
                  selected: {_splitType},
                  onSelectionChanged: (s) =>
                      setState(() => _splitType = s.first),
                ),
                const SizedBox(height: AppSpacing.sm),
                if (_splitType == SplitType.equal && equalPreview.isNotEmpty)
                  Container(
                    key: const Key('group_expense_equal_preview'),
                    padding: const EdgeInsets.all(AppSpacing.xs),
                    decoration: BoxDecoration(
                      color: AppColors.primaryContainer.withValues(alpha: 0.35),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: equalPreview.map((entry) {
                        final member = widget.group.members.firstWhere(
                          (m) =>
                              m.userId.trim().toLowerCase() == entry.userId,
                          orElse: () => widget.group.members.first,
                        );
                        return Text(
                          '${member.user.displayName}: ${formatVnd(entry.shareAmount)}',
                          style: AppTypography.bodyS,
                        );
                      }).toList(),
                    ),
                  ),
                if (_splitType == SplitType.custom)
                  ...widget.group.members.map((m) {
                    return Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
                      child: AppTextField(
                        key: Key('group_expense_custom_input_${m.userId}'),
                        controller: _customCtrls[m.userId],
                        labelText: '${m.user.displayName} (VND)',
                        keyboardType: TextInputType.number,
                      ),
                    );
                  }),
                if (_customError != null) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    _customError!,
                    style: AppTypography.bodyS.copyWith(color: AppColors.error),
                  ),
                ],
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
          key: const Key('group_expense_submit_button'),
          text: 'Lưu khoản chi',
          isFullWidth: false,
          onPressed: _submit,
        ),
      ],
    );
  }
}
