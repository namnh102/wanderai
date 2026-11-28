import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/network/api_error.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_badge.dart';
import '../../../core/widgets/app_button.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/app_error_state.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/app_state_banner.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../../trips/providers/trip_provider.dart';
import '../data/notification_models.dart';
import '../providers/notification_provider.dart';

class TripInviteDetailScreen extends ConsumerStatefulWidget {
  final String inviteId;

  const TripInviteDetailScreen({super.key, required this.inviteId});

  @override
  ConsumerState<TripInviteDetailScreen> createState() =>
      _TripInviteDetailScreenState();
}

class _TripInviteDetailScreenState
    extends ConsumerState<TripInviteDetailScreen> {
  TripInviteDetailModel? _invite;
  bool _isLoading = true;
  bool _isSubmitting = false;
  String? _errorMessage;
  String? _actionErrorMessage;

  @override
  void initState() {
    super.initState();
    Future.microtask(_loadInvite);
  }

  Future<void> _loadInvite() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
      _actionErrorMessage = null;
    });
    try {
      final detail = await ref
          .read(notificationRepositoryProvider)
          .getTripInviteDetail(widget.inviteId);
      if (!mounted) return;
      setState(() {
        _invite = detail;
        _isLoading = false;
      });
      final notifId = detail.notificationId;
      if (notifId != null && notifId.isNotEmpty) {
        await ref.read(notificationsProvider.notifier).markRead(notifId);
      }
    } on DioException catch (e) {
      if (!mounted) return;
      final details = ApiErrorDetails.fromDioException(e);
      setState(() {
        _isLoading = false;
        _errorMessage =
            details.message ?? 'Không thể tải thông tin lời mời chuyến đi.';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _errorMessage = 'Không thể tải thông tin lời mời chuyến đi.';
      });
    }
  }

  Future<void> _handleAccept(TripInviteDetailModel invite) async {
    if (_isSubmitting) return;
    setState(() {
      _isSubmitting = true;
      _actionErrorMessage = null;
    });

    final res = await ref
        .read(notificationsProvider.notifier)
        .acceptTripInvite(invite.id);
    if (!mounted) return;

    if (res.tripId != null && res.tripId!.isNotEmpty) {
      await ref.read(tripListProvider.notifier).loadTrips();
      if (!mounted) return;
      setState(() {
        _isSubmitting = false;
        if (res.invite != null) {
          _invite = res.invite;
        }
      });
      context.pushReplacement('/trips/${res.tripId}');
      return;
    }

    setState(() {
      _isSubmitting = false;
      _actionErrorMessage = res.errorMessage;
    });
    await _loadInvite();
  }

  Future<void> _handleDecline(TripInviteDetailModel invite) async {
    if (_isSubmitting) return;
    setState(() {
      _isSubmitting = true;
      _actionErrorMessage = null;
    });

    final res = await ref
        .read(notificationsProvider.notifier)
        .declineTripInvite(invite.id);
    if (!mounted) return;

    setState(() {
      _isSubmitting = false;
      if (res.invite != null) {
        _invite = res.invite;
      } else {
        _actionErrorMessage = res.errorMessage;
      }
    });
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

  String _formatDateRange(DateTime? start, DateTime? end) {
    if (start == null) return 'Chưa chọn ngày cụ thể';
    final s = '${start.day}/${start.month}/${start.year}';
    if (end == null) return s;
    final e = '${end.day}/${end.month}/${end.year}';
    return '$s - $e';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.warmBackground,
      appBar: AppBar(
        title: const Text(
          'Lời mời chuyến đi',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      body: ResponsiveWrapper(
        maxWidth: 680,
        child: _buildBody(context),
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_isLoading && _invite == null) {
      return const AppLoading(message: 'Đang tải chi tiết lời mời...');
    }

    if (_errorMessage != null && _invite == null) {
      return AppErrorState(
        message: _errorMessage!,
        onRetry: _loadInvite,
      );
    }

    final invite = _invite!;
    final status = invite.status;

    return RefreshIndicator(
      onRefresh: _loadInvite,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(AppSpacing.md),
        children: [
          if (_actionErrorMessage != null) ...[
            AppStateBanner(
              key: const Key('trip_invite_action_error_banner'),
              tone: AppStateBannerTone.error,
              message: _actionErrorMessage!,
            ),
            const SizedBox(height: AppSpacing.md),
          ],
          if (status == TripInviteStatus.revoked) ...[
            const AppStateBanner(
              key: Key('trip_invite_revoked_banner'),
              tone: AppStateBannerTone.warning,
              message:
                  'Lời mời tham gia chuyến đi này đã được chủ chuyến thu hồi. Bạn không thể chấp nhận lời mời đã thu hồi.',
            ),
            const SizedBox(height: AppSpacing.md),
          ] else if (status == TripInviteStatus.declined) ...[
            const AppStateBanner(
              key: Key('trip_invite_declined_banner'),
              tone: AppStateBannerTone.info,
              message: 'Bạn đã từ chối lời mời tham gia chuyến đi này.',
            ),
            const SizedBox(height: AppSpacing.md),
          ] else if (status == TripInviteStatus.accepted) ...[
            const AppStateBanner(
              key: Key('trip_invite_accepted_banner'),
              tone: AppStateBannerTone.info,
              message: 'Bạn đã tham gia chuyến đi này.',
            ),
            const SizedBox(height: AppSpacing.md),
          ],
          AppCard(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    AppBadge(
                      key: const Key('trip_invite_detail_status_badge'),
                      label: status.labelVi,
                      color: _statusColor(status),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.mdSmall),
                Text(
                  invite.tripTitle,
                  key: const Key('trip_invite_detail_trip_title'),
                  style: AppTypography.h2,
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Người mời: ${invite.inviterDisplayName}',
                  key: const Key('trip_invite_detail_inviter'),
                  style: AppTypography.bodyM.copyWith(
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Divider(height: 24),
                if (invite.destinationName != null &&
                    invite.destinationName!.trim().isNotEmpty) ...[
                  Row(
                    children: [
                      const Icon(
                        Icons.location_on_outlined,
                        size: 18,
                        color: AppColors.primary,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          invite.destinationName!,
                          style: AppTypography.bodyM.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                ],
                Row(
                  children: [
                    const Icon(
                      Icons.calendar_today_outlined,
                      size: 18,
                      color: AppColors.textSecondary,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _formatDateRange(invite.startDate, invite.endDate),
                        style: AppTypography.bodyM,
                      ),
                    ),
                  ],
                ),
                if (invite.tripDescription != null &&
                    invite.tripDescription!.trim().isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text(
                    invite.tripDescription!,
                    style: AppTypography.bodyM.copyWith(
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
                const SizedBox(height: AppSpacing.lg),
                if (status == TripInviteStatus.pending)
                  Row(
                    children: [
                      Expanded(
                        child: AppButton(
                          key: const Key('trip_invite_decline_button'),
                          text: 'Từ chối',
                          variant: AppButtonVariant.secondary,
                          onPressed: _isSubmitting
                              ? null
                              : () => _handleDecline(invite),
                        ),
                      ),
                      const SizedBox(width: AppSpacing.sm),
                      Expanded(
                        flex: 2,
                        child: AppButton(
                          key: const Key('trip_invite_accept_button'),
                          text: 'Chấp nhận vào chuyến',
                          icon: Icons.check_circle_outline,
                          isLoading: _isSubmitting,
                          onPressed: _isSubmitting
                              ? null
                              : () => _handleAccept(invite),
                        ),
                      ),
                    ],
                  )
                else if (status == TripInviteStatus.accepted)
                  AppButton(
                    key: const Key('trip_invite_open_trip_button'),
                    text: 'Mở chuyến đi',
                    icon: Icons.luggage_outlined,
                    onPressed: () =>
                        context.pushReplacement('/trips/${invite.tripId}'),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
