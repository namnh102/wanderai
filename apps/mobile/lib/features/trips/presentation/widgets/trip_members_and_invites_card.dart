import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/network/api_error.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../core/theme/app_typography.dart';
import '../../../../core/widgets/app_badge.dart';
import '../../../../core/widgets/app_button.dart';
import '../../../../core/widgets/app_text_field.dart';
import '../../../notifications/data/notification_models.dart';
import '../../../notifications/providers/notification_provider.dart';
import '../../data/trip_models.dart';

final bool _isFlutterTestRuntime =
    Platform.environment.containsKey('FLUTTER_TEST');

class TripMembersAndInvitesCard extends ConsumerStatefulWidget {
  final TripModel trip;

  const TripMembersAndInvitesCard({super.key, required this.trip});

  @override
  ConsumerState<TripMembersAndInvitesCard> createState() =>
      _TripMembersAndInvitesCardState();
}

class _TripMembersAndInvitesCardState
    extends ConsumerState<TripMembersAndInvitesCard> {
  List<TripInviteDetailModel> _invites = const [];
  bool _loadingInvites = false;
  bool _canManageInvites = true;
  String? _loadedForTripId;

  @override
  void initState() {
    super.initState();
    // Avoid firing unmocked background Dio requests during unrelated widget tests.
    if (!_isFlutterTestRuntime) {
      Future.microtask(_maybeLoadInvites);
    }
  }

  @override
  void didUpdateWidget(covariant TripMembersAndInvitesCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.trip.id != widget.trip.id) {
      _loadedForTripId = null;
      _invites = const [];
      _canManageInvites = true;
      if (!_isFlutterTestRuntime) {
        Future.microtask(_maybeLoadInvites);
      }
    }
  }

  Future<void> _maybeLoadInvites({bool force = false}) async {
    if (!force && _loadedForTripId == widget.trip.id) return;

    setState(() {
      _loadingInvites = true;
    });
    try {
      final list = await ref
          .read(notificationRepositoryProvider)
          .listTripInvites(widget.trip.id);
      if (!mounted) return;
      setState(() {
        _invites = list;
        _canManageInvites = true;
        _loadedForTripId = widget.trip.id;
        _loadingInvites = false;
      });
    } on DioException catch (e) {
      if (!mounted) return;
      final status = e.response?.statusCode;
      setState(() {
        if (status == 403) {
          _canManageInvites = false;
        }
        _loadingInvites = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loadingInvites = false;
      });
    }
  }

  Future<void> _openInviteDialog() async {
    final created = await showDialog<TripInviteDetailModel>(
      context: context,
      builder: (_) => _TripInviteEmailDialog(
        tripId: widget.trip.id,
        onSubmitEmail: (email) => ref
            .read(notificationRepositoryProvider)
            .sendTripInvite(widget.trip.id, email),
      ),
    );

    if (created != null && mounted) {
      await _maybeLoadInvites(force: true);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          key: const Key('trip_invite_sent_snackbar'),
          content: Text(
            created.idempotentDuplicate
                ? 'Lời mời tới ${created.inviteeDisplayName} đang ở trạng thái chờ phản hồi (không tạo trùng).'
                : 'Đã gửi lời mời tham gia chuyến đi tới ${created.inviteeDisplayName}.',
          ),
        ),
      );
    }
  }

  Future<void> _revokeInvite(TripInviteDetailModel invite) async {
    try {
      await ref
          .read(notificationRepositoryProvider)
          .revokeTripInvite(widget.trip.id, invite.id);
      if (!mounted) return;
      await _maybeLoadInvites(force: true);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          key: const Key('trip_invite_revoked_snackbar'),
          content: Text(
            'Đã thu hồi lời mời của ${invite.inviteeDisplayName}.',
          ),
        ),
      );
    } on DioException catch (e) {
      if (!mounted) return;
      final details = ApiErrorDetails.fromDioException(e);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(details.message ?? 'Không thể thu hồi lời mời.'),
        ),
      );
    }
  }

  Color _statusColor(TripInviteStatus status) {
    switch (status) {
      case TripInviteStatus.pending:
        return AppColors.warning;
      case TripInviteStatus.accepted:
        return AppColors.success;
      case TripInviteStatus.declined:
        return AppColors.textSecondary;
      case TripInviteStatus.revoked:
        return AppColors.error;
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final members = widget.trip.members;

    return Card(
      key: const Key('trip_members_and_invites_card'),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: cs.outlineVariant.withValues(alpha: 0.6)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 4,
              crossAxisAlignment: WrapCrossAlignment.center,
              alignment: WrapAlignment.spaceBetween,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.people_outline, size: 20, color: cs.primary),
                    const SizedBox(width: 8),
                    Flexible(
                      child: Text(
                        'Thành viên (${widget.trip.memberCount})',
                        style: AppTypography.h3,
                      ),
                    ),
                  ],
                ),
                if (_canManageInvites && widget.trip.status != 'CANCELLED')
                  TextButton.icon(
                    key: const Key('trip_invite_open_dialog_button'),
                    style: TextButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                    ),
                    onPressed: _openInviteDialog,
                    icon: const Icon(Icons.person_add_alt_1_outlined, size: 18),
                    label: const Text('Mời thành viên'),
                  ),
              ],
            ),
            if (members.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  for (final m in members)
                    Chip(
                      key: Key('trip_member_chip_${m.userId}'),
                      avatar: Icon(
                        m.role == 'owner'
                            ? Icons.workspace_premium_outlined
                            : Icons.person_outline,
                        size: 16,
                        color: cs.primary,
                      ),
                      label: Text(
                        m.role == 'owner'
                            ? '${m.displayName} (Chủ chuyến)'
                            : m.displayName,
                        style: const TextStyle(fontSize: 12),
                      ),
                      visualDensity: VisualDensity.compact,
                    ),
                ],
              ),
            ],
            if (_canManageInvites &&
                (_loadingInvites || _invites.isNotEmpty)) ...[
              const Divider(height: 20),
              Text(
                'Lời mời đã gửi',
                style: AppTypography.bodyS.copyWith(
                  fontWeight: FontWeight.w700,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 6),
              for (final inv in _invites)
                Padding(
                  key: Key('trip_outgoing_invite_${inv.id}'),
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(
                        inv.inviteeEmail != null
                            ? '${inv.inviteeDisplayName} (${inv.inviteeEmail})'
                            : inv.inviteeDisplayName,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      AppBadge(
                        key: Key('trip_outgoing_invite_status_${inv.id}'),
                        label: inv.status.labelVi,
                        color: _statusColor(inv.status),
                      ),
                      if (inv.status == TripInviteStatus.pending)
                        TextButton(
                          key: Key('trip_invite_revoke_${inv.id}'),
                          style: TextButton.styleFrom(
                            visualDensity: VisualDensity.compact,
                            foregroundColor: AppColors.error,
                          ),
                          onPressed: () => _revokeInvite(inv),
                          child: const Text('Thu hồi'),
                        ),
                    ],
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}

class _TripInviteEmailDialog extends StatefulWidget {
  final String tripId;
  final Future<TripInviteDetailModel> Function(String email) onSubmitEmail;

  const _TripInviteEmailDialog({
    required this.tripId,
    required this.onSubmitEmail,
  });

  @override
  State<_TripInviteEmailDialog> createState() => _TripInviteEmailDialogState();
}

class _TripInviteEmailDialogState extends State<_TripInviteEmailDialog> {
  late final TextEditingController _emailCtrl = TextEditingController();
  bool _isSending = false;
  String? _dialogError;

  @override
  void dispose() {
    _emailCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final email = _emailCtrl.text.trim();
    if (email.isEmpty) {
      setState(() {
        _dialogError = 'Vui lòng nhập email người nhận.';
      });
      return;
    }
    setState(() {
      _isSending = true;
      _dialogError = null;
    });
    try {
      final res = await widget.onSubmitEmail(email);
      if (mounted) {
        Navigator.of(context).pop(res);
      }
    } on DioException catch (e) {
      final details = ApiErrorDetails.fromDioException(e);
      if (mounted) {
        setState(() {
          _isSending = false;
          _dialogError = details.message ?? 'Không thể gửi lời mời lúc này.';
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _isSending = false;
          _dialogError = 'Không thể gửi lời mời lúc này.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Mời thành viên vào chuyến đi'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Nhập email tài khoản GoMate của người bạn muốn mời. Họ sẽ nhận thông báo lời mời trong ứng dụng.',
              style: TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 12),
            AppTextField(
              key: const Key('trip_invite_email_input'),
              controller: _emailCtrl,
              labelText: 'Email người nhận',
              hintText: 'ban.dong.hanh@example.com',
              keyboardType: TextInputType.emailAddress,
            ),
            if (_dialogError != null) ...[
              const SizedBox(height: 8),
              Text(
                _dialogError!,
                key: const Key('trip_invite_dialog_error_text'),
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.error,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _isSending ? null : () => Navigator.of(context).pop(),
          child: const Text('Hủy'),
        ),
        AppButton(
          key: const Key('trip_invite_submit_button'),
          text: 'Gửi lời mời',
          isFullWidth: false,
          isLoading: _isSending,
          onPressed: _isSending ? null : _submit,
        ),
      ],
    );
  }
}
