import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../core/theme/app_typography.dart';
import '../../../core/widgets/app_badge.dart';
import '../../../core/widgets/app_card.dart';
import '../../../core/widgets/app_empty_state.dart';
import '../../../core/widgets/app_error_state.dart';
import '../../../core/widgets/app_loading.dart';
import '../../../core/widgets/responsive_wrapper.dart';
import '../data/notification_models.dart';
import '../providers/notification_provider.dart';

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() =>
      _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      if (mounted) {
        ref.read(notificationsProvider.notifier).load();
      }
    });
  }

  Color _statusBadgeColor(TripInviteStatus status) {
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

  void _onTapNotification(
    BuildContext context,
    AppNotificationModel item,
  ) {
    if (!item.isRead) {
      unawaited(ref.read(notificationsProvider.notifier).markRead(item.id));
    }

    if (item.isTripInvite) {
      final inviteId = item.effectiveInviteId;
      final tripId = item.effectiveTripId;
      final status = item.effectiveInviteStatus;

      if (status == TripInviteStatus.accepted &&
          tripId != null &&
          tripId.isNotEmpty) {
        context.push('/trips/$tripId');
        return;
      }
      if (inviteId != null && inviteId.isNotEmpty) {
        context.push('/trips/invites/$inviteId');
        return;
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(notificationsProvider);

    return Scaffold(
      backgroundColor: AppColors.warmBackground,
      appBar: AppBar(
        title: const Text(
          'Thông báo',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        actions: [
          if (state.unreadCount > 0)
            TextButton(
              key: const Key('notifications_mark_all_read_button'),
              onPressed: () =>
                  ref.read(notificationsProvider.notifier).markAllRead(),
              child: const Text('Đọc tất cả'),
            ),
        ],
      ),
      body: ResponsiveWrapper(
        maxWidth: 720,
        child: RefreshIndicator(
          onRefresh: () => ref.read(notificationsProvider.notifier).load(),
          child: _buildBody(context, state),
        ),
      ),
    );
  }

  Widget _buildBody(BuildContext context, NotificationsState state) {
    if (state.isLoading && state.items.isEmpty) {
      return const AppLoading(message: 'Đang tải thông báo...');
    }

    if (state.errorMessage != null && state.items.isEmpty) {
      return AppErrorState(
        message: state.errorMessage!,
        onRetry: () => ref.read(notificationsProvider.notifier).load(),
      );
    }

    if (state.items.isEmpty) {
      return LayoutBuilder(
        builder: (context, constraints) => SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: ConstrainedBox(
            constraints: BoxConstraints(minHeight: constraints.maxHeight),
            child: const AppEmptyState(
              icon: Icons.notifications_none_rounded,
              title: 'Chưa có thông báo mới',
              description:
                  'Khi có lời mời tham gia chuyến đi hoặc cập nhật mới, bạn sẽ thấy ngay tại đây.',
            ),
          ),
        ),
      );
    }

    return ListView.separated(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(AppSpacing.md),
      itemCount: state.items.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        final item = state.items[index];
        final isInvite = item.isTripInvite;
        final inviteStatus = item.effectiveInviteStatus;

        return AppCard(
          key: Key('notification_item_${item.id}'),
          onTap: () => _onTapNotification(context, item),
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: item.isRead
                      ? AppColors.surfaceContainer
                      : AppColors.primaryContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  isInvite
                      ? Icons.card_travel_rounded
                      : Icons.notifications_outlined,
                  color: item.isRead
                      ? AppColors.textSecondary
                      : AppColors.primary,
                  size: 20,
                ),
              ),
              const SizedBox(width: AppSpacing.mdSmall),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            item.title,
                            style: AppTypography.h3.copyWith(
                              fontWeight: item.isRead
                                  ? FontWeight.w600
                                  : FontWeight.w700,
                            ),
                          ),
                        ),
                        if (!item.isRead)
                          Container(
                            key: Key('notification_unread_dot_${item.id}'),
                            width: 9,
                            height: 9,
                            margin: const EdgeInsets.only(left: 8),
                            decoration: const BoxDecoration(
                              color: AppColors.primary,
                              shape: BoxShape.circle,
                            ),
                          ),
                      ],
                    ),
                    if (item.body != null && item.body!.trim().isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        item.body!,
                        style: AppTypography.bodyM.copyWith(
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ],
                    if (isInvite) ...[
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          AppBadge(
                            key: Key('notification_invite_status_${item.id}'),
                            label: inviteStatus.labelVi,
                            color: _statusBadgeColor(inviteStatus),
                          ),
                          const Spacer(),
                          Text(
                            inviteStatus == TripInviteStatus.pending
                                ? 'Xem & phản hồi'
                                : (inviteStatus == TripInviteStatus.accepted
                                    ? 'Mở chuyến đi'
                                    : 'Xem chi tiết'),
                            style: AppTypography.bodyS.copyWith(
                              color: AppColors.primary,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          const SizedBox(width: 2),
                          const Icon(
                            Icons.chevron_right_rounded,
                            size: 16,
                            color: AppColors.primary,
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
