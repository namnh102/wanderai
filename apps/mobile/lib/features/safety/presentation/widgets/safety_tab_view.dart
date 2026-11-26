import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_radius.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_badge.dart';
import '../../../../core/widgets/app_button.dart';
import '../../../../core/widgets/app_card.dart';
import '../../../../core/widgets/app_empty_state.dart';
import '../../../../core/widgets/app_state_banner.dart';
import '../../../../core/widgets/app_text_field.dart';
import '../../../location/providers/user_location_provider.dart';
import '../../data/safety_models.dart';
import '../../providers/safety_provider.dart';

class SafetyConfirmPayload {
  final String title;
  final String description;
  final String? authorityOrRelation;
  final String? coordinationNote;
  final String confirmLabel;
  final bool isSandboxMode;
  final String? gpsSummary;

  const SafetyConfirmPayload({
    required this.title,
    required this.description,
    this.authorityOrRelation,
    this.coordinationNote,
    this.confirmLabel = 'Xác nhận',
    required this.isSandboxMode,
    this.gpsSummary,
  });
}

Future<bool> showSafetyConfirmDialog(
  BuildContext context,
  SafetyConfirmPayload payload,
) async {
  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: true,
    builder: (_) => _SafetyConfirmDialog(payload: payload),
  );
  return result == true;
}

class _SafetyConfirmDialog extends StatefulWidget {
  final SafetyConfirmPayload payload;
  const _SafetyConfirmDialog({required this.payload});

  @override
  State<_SafetyConfirmDialog> createState() => _SafetyConfirmDialogState();
}

class _SafetyConfirmDialogState extends State<_SafetyConfirmDialog> {
  bool _submitted = false;

  void _handleProceed() {
    if (_submitted) return;
    setState(() => _submitted = true);
    Navigator.of(context).pop(true);
  }

  void _handleCancel() {
    if (_submitted) return;
    Navigator.of(context).pop(false);
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.payload;
    return AlertDialog(
      key: const Key('safety_confirm_dialog'),
      title: Text(p.title, style: AppTypography.h3),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(p.description, style: AppTypography.bodyM),
            if (p.authorityOrRelation != null &&
                p.authorityOrRelation!.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                p.authorityOrRelation!,
                style:
                    AppTypography.bodyS.copyWith(color: AppColors.textSecondary),
              ),
            ],
            if (p.coordinationNote != null &&
                p.coordinationNote!.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.xs),
              Text(
                p.coordinationNote!,
                style: AppTypography.caption
                    .copyWith(color: AppColors.textSecondary),
              ),
            ],
            const SizedBox(height: AppSpacing.sm),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: const BoxDecoration(
                color: AppColors.surfaceContainer,
                borderRadius: AppRadius.smRadius,
              ),
              child: Text(
                p.gpsSummary ?? 'Chưa có tọa độ GPS hiện tại',
                style: AppTypography.caption.copyWith(
                  color: AppColors.textPrimary,
                ),
              ),
            ),
            if (p.isSandboxMode) ...[
              const SizedBox(height: AppSpacing.sm),
              const AppBadge(
                label: 'Chế độ kiểm thử (Sandbox) — Không gọi số thật',
                icon: Icons.science_outlined,
                color: AppColors.warning,
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          key: const Key('safety_confirm_cancel'),
          onPressed: _submitted ? null : _handleCancel,
          child: const Text('Hủy'),
        ),
        ElevatedButton(
          key: const Key('safety_confirm_proceed'),
          style: ElevatedButton.styleFrom(
            backgroundColor: AppColors.error,
            foregroundColor: AppColors.onError,
          ),
          onPressed: _submitted ? null : _handleProceed,
          child: Text(p.confirmLabel),
        ),
      ],
    );
  }
}

class SafetyTabView extends ConsumerStatefulWidget {
  const SafetyTabView({super.key});

  @override
  ConsumerState<SafetyTabView> createState() => _SafetyTabViewState();
}

class _SafetyTabViewState extends ConsumerState<SafetyTabView> {
  bool _isDialogOpen = false;

  String? _formatGpsSummary(UserLocationState locState) {
    final fix = locState.fix;
    if (fix == null) return null;
    final lat = fix.latitude.toStringAsFixed(6);
    final lng = fix.longitude.toStringAsFixed(6);
    final acc = fix.accuracyMeters.round();
    return 'Vị trí hiện tại: $lat, $lng (±$acc m)';
  }

  Future<bool> _confirmAction(SafetyConfirmPayload payload) async {
    if (_isDialogOpen) return false;
    _isDialogOpen = true;
    try {
      return await showSafetyConfirmDialog(context, payload);
    } finally {
      _isDialogOpen = false;
    }
  }

  Future<void> _runSafeTrigger(Future<void> Function() action) async {
    try {
      await action();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.maybeOf(context)?.showSnackBar(
        const SnackBar(
          content: Text(
            'Không thể thực hiện thao tác khẩn cấp lúc này. Vui lòng thử lại.',
          ),
        ),
      );
    }
  }

  Future<void> _onTriggerDirectoryDial(EmergencyDirectoryEntry entry) async {
    final safetyState = ref.read(safetyProvider);
    if (_isDialogOpen || safetyState.isTriggerInFlight) return;
    final locState = ref.read(userLocationProvider);

    final confirmed = await _confirmAction(
      SafetyConfirmPayload(
        title: safetyState.isSandboxMode
            ? 'Xác nhận kiểm thử ${entry.displayNumber}?'
            : 'Xác nhận gọi ${entry.displayNumber}?',
        description: '${entry.displayNumber} — ${entry.displayName}',
        authorityOrRelation: entry.governingAuthority,
        coordinationNote: entry.coordinationNote,
        confirmLabel: 'Xác nhận',
        isSandboxMode: safetyState.isSandboxMode,
        gpsSummary: _formatGpsSummary(locState),
      ),
    );
    if (!confirmed || !mounted) return;

    await _runSafeTrigger(
      () => ref.read(safetyProvider.notifier).triggerEmergencyAction(
            actionType: 'dial',
            targetNumber: entry.phoneNumber,
            targetLabel: entry.displayName,
            latitude: locState.fix?.latitude,
            longitude: locState.fix?.longitude,
          ),
    );
  }

  Future<void> _onTriggerContactDial(PersonalSafetyContact contact) async {
    final safetyState = ref.read(safetyProvider);
    if (_isDialogOpen || safetyState.isTriggerInFlight) return;
    final locState = ref.read(userLocationProvider);

    final confirmed = await _confirmAction(
      SafetyConfirmPayload(
        title: 'Gọi người liên hệ tin cậy?',
        description: '${contact.name} (${contact.phone})',
        authorityOrRelation:
            'Quan hệ: ${PersonalSafetyContact.relationLabel(contact.relation)}',
        confirmLabel: 'Xác nhận',
        isSandboxMode: safetyState.isSandboxMode,
        gpsSummary: _formatGpsSummary(locState),
      ),
    );
    if (!confirmed || !mounted) return;

    await _runSafeTrigger(
      () => ref.read(safetyProvider.notifier).triggerEmergencyAction(
            actionType: 'dial',
            targetNumber: contact.phone,
            targetLabel: contact.name,
            latitude: locState.fix?.latitude,
            longitude: locState.fix?.longitude,
          ),
    );
  }

  Future<void> _onTriggerSos() async {
    final safetyState = ref.read(safetyProvider);
    if (_isDialogOpen || safetyState.isTriggerInFlight) return;
    final locState = ref.read(userLocationProvider);

    final confirmed = await _confirmAction(
      SafetyConfirmPayload(
        title: safetyState.isSandboxMode
            ? 'Xác nhận SOS (Kiểm thử)?'
            : 'Xác nhận gửi tín hiệu SOS?',
        description: safetyState.isSandboxMode
            ? 'Ghi nhận sự kiện SOS mô phỏng và kiểm tra đồng bộ máy chủ.'
            : 'Gửi sự kiện SOS kèm tọa độ hiện tại lên máy chủ GoMate.',
        confirmLabel: 'Xác nhận',
        isSandboxMode: safetyState.isSandboxMode,
        gpsSummary: _formatGpsSummary(locState),
      ),
    );
    if (!confirmed || !mounted) return;

    await _runSafeTrigger(
      () => ref.read(safetyProvider.notifier).triggerEmergencyAction(
            actionType: 'sos',
            targetNumber: 'SOS',
            targetLabel: 'Tín hiệu SOS khẩn cấp',
            latitude: locState.fix?.latitude,
            longitude: locState.fix?.longitude,
            syncToServer: true,
          ),
    );
  }

  Future<void> _onDeleteContact(PersonalSafetyContact contact) async {
    final safetyState = ref.read(safetyProvider);
    if (_isDialogOpen || safetyState.isSavingData) return;

    final confirmed = await _confirmAction(
      SafetyConfirmPayload(
        title: 'Xóa người liên hệ tin cậy?',
        description:
            'Xóa "${contact.name}" (${contact.phone}) khỏi danh sách an toàn cá nhân?',
        confirmLabel: 'Xác nhận',
        isSandboxMode: false,
      ),
    );
    if (!confirmed || !mounted) return;

    await ref.read(safetyProvider.notifier).removeContact(contact.id);
  }

  Future<void> _openAddContactDialog() async {
    final result =
        await showDialog<({String name, String phone, String relation})>(
      context: context,
      builder: (_) => const _AddContactDialog(),
    );

    if (result != null && mounted) {
      await ref.read(safetyProvider.notifier).addContact(
            name: result.name,
            phone: result.phone,
            relation: result.relation,
          );
    }
  }

  Future<void> _openAddNoteDialog() async {
    final result =
        await showDialog<({String title, String note, bool syncOnline})>(
      context: context,
      builder: (_) => const _AddNoteDialog(),
    );

    if (result != null && mounted) {
      final locState = ref.read(userLocationProvider);
      await ref.read(safetyProvider.notifier).addCheckinNote(
            title: result.title,
            note: result.note,
            latitude: locState.fix?.latitude,
            longitude: locState.fix?.longitude,
            locationLabel: _formatGpsSummary(locState),
            syncOnline: result.syncOnline,
          );
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(safetyProvider);
    final locState = ref.watch(userLocationProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
        AppStateBanner(
          key: const Key('safety_network_banner'),
          tone: state.isOffline
              ? AppStateBannerTone.warning
              : AppStateBannerTone.info,
          icon: state.isOffline
              ? Icons.wifi_off_rounded
              : Icons.cloud_done_outlined,
          message: state.isOffline
              ? 'Đang ngoại tuyến (mất mạng) — Danh bạ khẩn cấp tích hợp sẵn và dữ liệu an toàn đã lưu trên thiết bị vẫn hoạt động bình thường.'
              : 'Đang trực tuyến — Sẵn sàng đồng bộ check-in và sự kiện an toàn lên máy chủ.',
          actionLabel: 'Kiểm tra mạng',
          onAction: () =>
              ref.read(safetyProvider.notifier).refreshConnectivity(),
        ),
        const SizedBox(height: AppSpacing.sm),
        AppCard(
          key: const Key('safety_sandbox_card'),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.xs,
          ),
          child: SwitchListTile(
            key: const Key('safety_sandbox_switch'),
            contentPadding: EdgeInsets.zero,
            title: const Text(
              'Chế độ kiểm thử (Sandbox)',
              style: AppTypography.h3,
            ),
            subtitle: Text(
              state.isSandboxMode
                  ? 'Chế độ kiểm thử (Sandbox) — Không gọi số khẩn cấp thật'
                  : 'Chế độ gọi trực tiếp qua trình quay số của thiết bị (luôn hỏi xác nhận trước).',
              style: AppTypography.bodyS,
            ),
            value: state.isSandboxMode,
            onChanged: (value) =>
                ref.read(safetyProvider.notifier).setSandboxMode(value),
          ),
        ),
        if (state.lastActionBannerMessage != null) ...[
          const SizedBox(height: AppSpacing.sm),
          AppStateBanner(
            key: const Key('safety_last_action_status'),
            tone: _bannerToneForStatus(state.lastActionStatus),
            icon: _bannerIconForStatus(state.lastActionStatus),
            message: state.lastActionBannerMessage!,
          ),
        ],
        if (state.errorMessage != null) ...[
          const SizedBox(height: AppSpacing.sm),
          AppStateBanner(
            key: const Key('safety_error_banner'),
            tone: AppStateBannerTone.error,
            message: state.errorMessage!,
          ),
        ],
        const SizedBox(height: AppSpacing.md),
        AppCard(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Expanded(
                    child: Text(
                      'Trung tâm SOS & Kiểm tra kết nối',
                      style: AppTypography.h3,
                    ),
                  ),
                  if (state.isSandboxMode)
                    const AppBadge(
                      label: 'Sandbox',
                      icon: Icons.science_outlined,
                      color: AppColors.warning,
                    ),
                ],
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                'Luôn yêu cầu xác nhận trước khi thực hiện và bảo vệ chống chạm lặp nhiều lần.',
                style:
                    AppTypography.bodyS.copyWith(color: AppColors.textSecondary),
              ),
              const SizedBox(height: AppSpacing.sm),
              AppButton(
                key: const Key('safety_sos_button'),
                text: state.isSandboxMode
                    ? 'Kích hoạt SOS (Chế độ kiểm thử)'
                    : 'Gửi tín hiệu SOS khẩn cấp',
                icon: Icons.sos_rounded,
                variant: AppButtonVariant.danger,
                isLoading: state.isTriggerInFlight,
                onPressed: state.isTriggerInFlight ? null : _onTriggerSos,
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        const Text('Danh bạ khẩn cấp quốc gia', style: AppTypography.h3),
        const SizedBox(height: AppSpacing.xs),
        Text(
          'Các đầu số cứu nạn chính thức của Việt Nam (tích hợp sẵn ngoại tuyến).',
          style: AppTypography.bodyS.copyWith(color: AppColors.textSecondary),
        ),
        const SizedBox(height: AppSpacing.sm),
        for (final entry in state.nationalEntries) ...[
          _DirectoryEntryCard(
            entry: entry,
            onTap: () => _onTriggerDirectoryDial(entry),
          ),
          const SizedBox(height: AppSpacing.sm),
        ],
        if (state.protectionEntries.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          const Text(
            'Đường dây nóng bảo vệ xã hội',
            style: AppTypography.h3,
          ),
          const SizedBox(height: AppSpacing.sm),
          for (final entry in state.protectionEntries) ...[
            _DirectoryEntryCard(
              entry: entry,
              onTap: () => _onTriggerDirectoryDial(entry),
            ),
            const SizedBox(height: AppSpacing.sm),
          ],
        ],
        if (state.touristSupportEntries.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          const Text(
            'Hỗ trợ du khách địa phương',
            style: AppTypography.h3,
          ),
          const SizedBox(height: AppSpacing.sm),
          for (final entry in state.touristSupportEntries) ...[
            _DirectoryEntryCard(
              entry: entry,
              onTap: () => _onTriggerDirectoryDial(entry),
            ),
            const SizedBox(height: AppSpacing.sm),
          ],
        ],
        const SizedBox(height: AppSpacing.md),
        _ForegroundGpsCard(
          locState: locState,
          onRefresh: () => ref.read(userLocationProvider.notifier).request(),
          onCopy: locState.fix == null
              ? null
              : () async {
                  final fix = locState.fix!;
                  final coords =
                      '${fix.latitude.toStringAsFixed(6)}, ${fix.longitude.toStringAsFixed(6)}';
                  await Clipboard.setData(ClipboardData(text: coords));
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text('Đã sao chép tọa độ: $coords'),
                      ),
                    );
                  }
                },
          onOpenSettings: () =>
              ref.read(userLocationProvider.notifier).openAppSettings(),
        ),
        const SizedBox(height: AppSpacing.lg),
        Row(
          children: [
            const Expanded(
              child: Text(
                'Dữ liệu an toàn cá nhân',
                style: AppTypography.h3,
              ),
            ),
            Text(
              '${state.contacts.length}/$kMaxPersonalSafetyContacts liên hệ',
              style:
                  AppTypography.caption.copyWith(color: AppColors.textSecondary),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        Row(
          children: [
            Expanded(
              child: AppButton(
                key: const Key('safety_add_contact_button'),
                text: 'Thêm liên hệ',
                icon: Icons.person_add_alt_1_outlined,
                variant: AppButtonVariant.secondary,
                onPressed: (state.isSavingData ||
                        state.contacts.length >= kMaxPersonalSafetyContacts)
                    ? null
                    : _openAddContactDialog,
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: AppButton(
                key: const Key('safety_add_note_button'),
                text: 'Thêm check-in',
                icon: Icons.edit_note_rounded,
                variant: AppButtonVariant.tonal,
                onPressed: state.isSavingData ? null : _openAddNoteDialog,
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        if (!state.hasPersonalData)
          state.isOffline
              ? AppEmptyState(
                  key: const Key('safety_empty_offline_state'),
                  icon: Icons.cloud_off_rounded,
                  title: 'Chưa có dữ liệu an toàn cá nhân trên thiết bị',
                  description:
                      'Thiết bị đang ngoại tuyến (mất mạng) và hiện chưa có người liên hệ tin cậy hay ghi chú check-in nào được lưu. Danh bạ khẩn cấp tích hợp sẵn bên trên vẫn sẵn sàng để dùng.',
                  actionLabel: 'Lưu liên hệ ngoại tuyến',
                  onAction: _openAddContactDialog,
                )
              : AppEmptyState(
                  key: const Key('safety_empty_online_state'),
                  icon: Icons.shield_outlined,
                  title: 'Chưa có dữ liệu an toàn cá nhân',
                  description:
                      'Thêm tối đa 3 người liên hệ tin cậy hoặc tạo ghi chú check-in an toàn để sử dụng ngay cả khi mất mạng.',
                  actionLabel: 'Thêm người liên hệ',
                  onAction: _openAddContactDialog,
                )
        else ...[
          if (state.contacts.isNotEmpty) ...[
            const Text('Người liên hệ tin cậy', style: AppTypography.h3),
            const SizedBox(height: AppSpacing.xs),
            for (final contact in state.contacts)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: AppCard(
                  key: Key('safety_contact_card_${contact.id}'),
                  onTap: () => _onTriggerContactDial(contact),
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Row(
                    children: [
                      const Icon(Icons.contact_phone_outlined,
                          color: AppColors.primary),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '${contact.name} · ${contact.phone}',
                              style: AppTypography.h3,
                            ),
                            const SizedBox(height: 2),
                            Text(
                              '${PersonalSafetyContact.relationLabel(contact.relation)} · ${contact.statusMessage ?? _shortStatusLabel(contact.sendStatus)}',
                              style: AppTypography.bodyS.copyWith(
                                color: AppColors.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        key: Key('safety_delete_contact_${contact.id}'),
                        tooltip: 'Xóa người liên hệ',
                        icon: const Icon(Icons.delete_outline_rounded,
                            color: AppColors.error),
                        onPressed: () => _onDeleteContact(contact),
                      ),
                    ],
                  ),
                ),
              ),
          ],
          if (state.notes.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            const Text('Ghi chú & Check-in an toàn', style: AppTypography.h3),
            const SizedBox(height: AppSpacing.xs),
            for (final note in state.notes)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: AppCard(
                  key: Key('safety_note_card_${note.id}'),
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(note.title, style: AppTypography.h3),
                          ),
                          AppBadge(
                            label: _shortStatusLabel(note.sendStatus),
                            color: _badgeColorForStatus(note.sendStatus),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(note.note, style: AppTypography.bodyM),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        note.statusMessage,
                        style: AppTypography.caption.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
          if (state.events.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.sm),
            const Text(
              'Nhật ký thao tác khẩn cấp / kiểm thử',
              style: AppTypography.h3,
            ),
            const SizedBox(height: AppSpacing.xs),
            Container(
              key: const Key('safety_event_log'),
              child: Column(
                children: [
                  for (final ev in state.events)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                      child: AppCard(
                        padding: const EdgeInsets.all(AppSpacing.md),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    '${ev.targetLabel} (${ev.targetNumber})',
                                    style: AppTypography.h3,
                                  ),
                                ),
                                AppBadge(
                                  label: _shortStatusLabel(ev.sendStatus),
                                  color: _badgeColorForStatus(ev.sendStatus),
                                ),
                              ],
                            ),
                            const SizedBox(height: AppSpacing.xs),
                            Text(
                              ev.statusMessage,
                              style: AppTypography.bodyS.copyWith(
                                color: AppColors.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ],
        const SizedBox(height: AppSpacing.lg),
        AppCard(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Thông tin viễn thông & Miễn trừ trách nhiệm',
                style: AppTypography.h3,
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                state.directoryBundle.offlineTelecomNotice,
                style: AppTypography.bodyS.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                state.directoryBundle.disclaimer,
                style: AppTypography.caption.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
            ],
          ),
        ),
        ],
      ),
    );
  }

  static AppStateBannerTone _bannerToneForStatus(
    SafetyNetworkSendStatus? status,
  ) {
    switch (status) {
      case SafetyNetworkSendStatus.notSentOffline:
      case SafetyNetworkSendStatus.dialerFailed:
        return AppStateBannerTone.warning;
      default:
        return AppStateBannerTone.info;
    }
  }

  static IconData _bannerIconForStatus(SafetyNetworkSendStatus? status) {
    switch (status) {
      case SafetyNetworkSendStatus.notSentOffline:
        return Icons.cloud_off_rounded;
      case SafetyNetworkSendStatus.dialerFailed:
        return Icons.warning_amber_rounded;
      case SafetyNetworkSendStatus.sandboxSimulated:
        return Icons.science_outlined;
      case SafetyNetworkSendStatus.sentOnline:
        return Icons.cloud_done_outlined;
      default:
        return Icons.info_outline_rounded;
    }
  }

  static String _shortStatusLabel(SafetyNetworkSendStatus status) {
    switch (status) {
      case SafetyNetworkSendStatus.sandboxSimulated:
        return 'Kiểm thử (Sandbox)';
      case SafetyNetworkSendStatus.sentOnline:
        return 'Đã gửi máy chủ';
      case SafetyNetworkSendStatus.notSentOffline:
        return 'Chưa gửi (mất mạng)';
      case SafetyNetworkSendStatus.localOnly:
        return 'Lưu cục bộ';
      case SafetyNetworkSendStatus.dialerOpened:
        return 'Đã mở quay số';
      case SafetyNetworkSendStatus.dialerFailed:
        return 'Không mở được quay số';
    }
  }

  static Color _badgeColorForStatus(SafetyNetworkSendStatus status) {
    switch (status) {
      case SafetyNetworkSendStatus.sentOnline:
      case SafetyNetworkSendStatus.dialerOpened:
        return AppColors.success;
      case SafetyNetworkSendStatus.notSentOffline:
      case SafetyNetworkSendStatus.sandboxSimulated:
        return AppColors.warning;
      case SafetyNetworkSendStatus.dialerFailed:
        return AppColors.error;
      case SafetyNetworkSendStatus.localOnly:
        return AppColors.primary;
    }
  }
}

class _DirectoryEntryCard extends StatelessWidget {
  final EmergencyDirectoryEntry entry;
  final VoidCallback onTap;

  const _DirectoryEntryCard({
    required this.entry,
    required this.onTap,
  });

  IconData _iconForEntry() {
    switch (entry.phoneNumber) {
      case '112':
        return Icons.emergency_share_outlined;
      case '113':
        return Icons.local_police_outlined;
      case '114':
        return Icons.local_fire_department_outlined;
      case '115':
        return Icons.medical_services_outlined;
      case '111':
        return Icons.child_care_outlined;
      default:
        return Icons.support_agent_outlined;
    }
  }

  @override
  Widget build(BuildContext context) {
    final isEmergencyCatA =
        entry.category == EmergencyCategory.emergencyNational;
    final accent = isEmergencyCatA ? AppColors.error : AppColors.primary;

    return AppCard(
      key: Key('safety_emergency_tile_${entry.phoneNumber}'),
      onTap: onTap,
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.12),
                  borderRadius: AppRadius.mdRadius,
                ),
                child: Icon(_iconForEntry(), color: accent),
              ),
              const SizedBox(width: AppSpacing.mdSmall),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${entry.displayNumber} — ${entry.displayName}',
                      style: AppTypography.h3,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      entry.governingAuthority,
                      style: AppTypography.caption.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(Icons.phone_forwarded_outlined, color: accent),
            ],
          ),
          if (entry.description != null && entry.description!.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xs),
            Text(
              entry.description!,
              style: AppTypography.bodyS.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
          if (entry.physicalAddress != null &&
              entry.physicalAddress!.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Địa chỉ: ${entry.physicalAddress}',
              style: AppTypography.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
          if (entry.dialNote != null && entry.dialNote!.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xs),
            Text(
              entry.dialNote!,
              style: AppTypography.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
          if (entry.secondaryPhone != null &&
              entry.secondaryPhone!.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Số phụ (chưa rõ cước): ${entry.secondaryPhone}',
              style: AppTypography.caption.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              if (entry.isVerified24x7)
                const AppBadge(
                  label: '24/7',
                  icon: Icons.schedule_rounded,
                  color: AppColors.success,
                ),
              if (entry.isVerifiedFree)
                const AppBadge(
                  label: 'Miễn phí',
                  icon: Icons.verified_outlined,
                  color: AppColors.primary,
                ),
              if (entry.hasUnknownMetadata)
                AppBadge(
                  label: entry.neutralBadge ?? 'Thông tin hỗ trợ du khách',
                  icon: Icons.info_outline_rounded,
                  color: AppColors.textSecondary,
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ForegroundGpsCard extends StatelessWidget {
  final UserLocationState locState;
  final VoidCallback onRefresh;
  final VoidCallback? onCopy;
  final VoidCallback onOpenSettings;

  const _ForegroundGpsCard({
    required this.locState,
    required this.onRefresh,
    required this.onCopy,
    required this.onOpenSettings,
  });

  @override
  Widget build(BuildContext context) {
    final fix = locState.fix;
    final String statusText;
    if (fix != null) {
      statusText =
          '${fix.latitude.toStringAsFixed(6)}, ${fix.longitude.toStringAsFixed(6)} · ${locState.label ?? ''}';
    } else if (locState.status == UserLocationStatus.denied &&
        locState.permissionState == LocationPermissionState.deniedForever) {
      statusText =
          'Quyền vị trí đã bị từ chối vĩnh viễn. Vẫn có thể gọi khẩn cấp bình thường.';
    } else if (locState.status == UserLocationStatus.denied) {
      statusText =
          'Chưa cấp quyền vị trí. Nhấn "Làm mới vị trí" để đọc tọa độ khi cần.';
    } else {
      statusText = 'Chưa lấy tọa độ GPS hiện tại (chỉ đọc khi mở màn hình).';
    }

    return AppCard(
      key: const Key('safety_gps_card'),
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Tọa độ GPS hiện tại (Foreground)',
              style: AppTypography.h3),
          const SizedBox(height: AppSpacing.xs),
          Text(
            statusText,
            style: AppTypography.bodyS.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.xs,
            children: [
              OutlinedButton.icon(
                key: const Key('safety_gps_refresh_button'),
                onPressed: locState.status == UserLocationStatus.requesting
                    ? null
                    : onRefresh,
                icon: const Icon(Icons.my_location_outlined, size: 16),
                label: const Text('Làm mới vị trí'),
              ),
              OutlinedButton.icon(
                key: const Key('safety_gps_copy_button'),
                onPressed: onCopy,
                icon: const Icon(Icons.copy_outlined, size: 16),
                label: const Text('Sao chép tọa độ'),
              ),
              if (locState.permissionState ==
                  LocationPermissionState.deniedForever)
                TextButton(
                  onPressed: onOpenSettings,
                  child: const Text('Mở Cài đặt hệ thống'),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _AddContactDialog extends StatefulWidget {
  const _AddContactDialog();

  @override
  State<_AddContactDialog> createState() => _AddContactDialogState();
}

class _AddContactDialogState extends State<_AddContactDialog> {
  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  String _relation = 'family';

  @override
  void dispose() {
    _nameCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      key: const Key('safety_add_contact_dialog'),
      title: const Text(
        'Thêm người liên hệ tin cậy',
        style: AppTypography.h3,
      ),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AppTextField(
              key: const Key('safety_contact_name_input'),
              controller: _nameCtrl,
              labelText: 'Họ và tên',
              hintText: 'Ví dụ: Minh Anh',
            ),
            const SizedBox(height: AppSpacing.sm),
            AppTextField(
              key: const Key('safety_contact_phone_input'),
              controller: _phoneCtrl,
              keyboardType: TextInputType.phone,
              labelText: 'Số điện thoại',
              hintText: 'Ví dụ: 0901234567',
            ),
            const SizedBox(height: AppSpacing.sm),
            DropdownButtonFormField<String>(
              key: const Key('safety_contact_relation_select'),
              initialValue: _relation,
              decoration: const InputDecoration(
                labelText: 'Mối quan hệ',
              ),
              items: const [
                DropdownMenuItem(value: 'family', child: Text('Gia đình')),
                DropdownMenuItem(value: 'friend', child: Text('Bạn bè')),
                DropdownMenuItem(
                    value: 'colleague', child: Text('Đồng nghiệp')),
                DropdownMenuItem(value: 'embassy', child: Text('Đại sứ quán')),
                DropdownMenuItem(value: 'other', child: Text('Khác')),
              ],
              onChanged: (val) {
                if (val != null) {
                  setState(() => _relation = val);
                }
              },
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Hủy'),
        ),
        ElevatedButton(
          key: const Key('safety_contact_save_button'),
          onPressed: () => Navigator.of(context).pop((
            name: _nameCtrl.text,
            phone: _phoneCtrl.text,
            relation: _relation,
          )),
          child: const Text('Lưu'),
        ),
      ],
    );
  }
}

class _AddNoteDialog extends StatefulWidget {
  const _AddNoteDialog();

  @override
  State<_AddNoteDialog> createState() => _AddNoteDialogState();
}

class _AddNoteDialogState extends State<_AddNoteDialog> {
  final _titleCtrl = TextEditingController(text: 'Check-in an toàn');
  final _noteCtrl = TextEditingController();
  bool _syncOnline = true;

  @override
  void dispose() {
    _titleCtrl.dispose();
    _noteCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      key: const Key('safety_add_note_dialog'),
      title: const Text(
        'Thêm ghi chú / Check-in an toàn',
        style: AppTypography.h3,
      ),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AppTextField(
              key: const Key('safety_note_title_input'),
              controller: _titleCtrl,
              labelText: 'Tiêu đề',
            ),
            const SizedBox(height: AppSpacing.sm),
            AppTextField(
              key: const Key('safety_note_body_input'),
              controller: _noteCtrl,
              labelText: 'Nội dung ghi chú',
              hintText: 'Ví dụ: Đã đến khách sạn an toàn',
              maxLines: 3,
            ),
            const SizedBox(height: AppSpacing.xs),
            CheckboxListTile(
              key: const Key('safety_note_sync_checkbox'),
              contentPadding: EdgeInsets.zero,
              title: const Text(
                'Gửi đồng bộ lên máy chủ',
                style: AppTypography.bodyS,
              ),
              value: _syncOnline,
              onChanged: (v) => setState(() => _syncOnline = v ?? true),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Hủy'),
        ),
        ElevatedButton(
          key: const Key('safety_note_save_button'),
          onPressed: () => Navigator.of(context).pop((
            title: _titleCtrl.text,
            note: _noteCtrl.text,
            syncOnline: _syncOnline,
          )),
          child: const Text('Lưu ghi chú'),
        ),
      ],
    );
  }
}
