import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../../../core/theme/app_colors.dart';
import '../../providers/notification_provider.dart';

/// AppBar notification bell displaying authoritative unread badge count.
class NotificationBellButton extends ConsumerWidget {
  const NotificationBellButton({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unreadCount =
        ref.watch(notificationsProvider.select((s) => s.unreadCount));
    final badgeText = unreadCount > 99 ? '99+' : '$unreadCount';

    return IconButton(
      key: const Key('app_notification_bell_button'),
      tooltip: 'Thông báo',
      visualDensity: VisualDensity.compact,
      onPressed: () => context.push('/notifications'),
      icon: Stack(
        clipBehavior: Clip.none,
        children: [
          Icon(
            unreadCount > 0
                ? Icons.notifications_active_outlined
                : Icons.notifications_none_rounded,
            color: AppColors.primary,
          ),
          if (unreadCount > 0)
            Positioned(
              right: -5,
              top: -4,
              child: Container(
                key: const Key('app_notification_unread_badge'),
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                constraints: const BoxConstraints(minWidth: 17, minHeight: 17),
                decoration: BoxDecoration(
                  color: AppColors.error,
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Text(
                  badgeText,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    height: 1.1,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Foreground single-flight in-app notification synchronizer mounted inside authenticated shell.
class NotificationAutoSyncHost extends ConsumerStatefulWidget {
  final bool enabled;
  final Widget child;

  const NotificationAutoSyncHost({
    super.key,
    required this.enabled,
    required this.child,
  });

  @override
  ConsumerState<NotificationAutoSyncHost> createState() =>
      _NotificationAutoSyncHostState();
}

class _NotificationAutoSyncHostState
    extends ConsumerState<NotificationAutoSyncHost>
    with WidgetsBindingObserver {
  Timer? _pollTimer;
  bool _syncInFlight = false;
  AppLifecycleState _lifecycleState = AppLifecycleState.resumed;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _lifecycleState =
        WidgetsBinding.instance.lifecycleState ?? AppLifecycleState.resumed;
    if (widget.enabled) {
      Future.microtask(_triggerImmediateAndSchedule);
    }
  }

  @override
  void didUpdateWidget(covariant NotificationAutoSyncHost oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!oldWidget.enabled && widget.enabled) {
      Future.microtask(_triggerImmediateAndSchedule);
    } else if (oldWidget.enabled && !widget.enabled) {
      _cancelTimer();
    }
  }

  bool get _isForeground =>
      _lifecycleState == AppLifecycleState.resumed ||
      _lifecycleState == AppLifecycleState.inactive;

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _lifecycleState = state;
    if (!_isForeground) {
      _cancelTimer();
    } else if (widget.enabled) {
      unawaited(_triggerImmediateAndSchedule());
    }
  }

  @override
  void dispose() {
    _cancelTimer();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  void _cancelTimer() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> _triggerImmediateAndSchedule() async {
    if (!mounted || !widget.enabled) return;
    if (!_isForeground) return;
    await _runSingleFlightTick();
  }

  Future<void> _runSingleFlightTick() async {
    if (!mounted || !widget.enabled) return;
    if (_syncInFlight) return;
    _cancelTimer();
    _syncInFlight = true;
    try {
      await ref.read(notificationsProvider.notifier).load(silent: true);
    } finally {
      _syncInFlight = false;
      _scheduleNextIfEligible();
    }
  }

  void _scheduleNextIfEligible() {
    _cancelTimer();
    if (!mounted || !widget.enabled) return;
    if (!_isForeground) return;
    final interval = ref.read(notificationPollIntervalProvider);
    if (interval == null || interval <= Duration.zero) return;

    _pollTimer = Timer(interval, () {
      _pollTimer = null;
      if (!mounted || !widget.enabled || !_isForeground) {
        return;
      }
      unawaited(_runSingleFlightTick());
    });
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
