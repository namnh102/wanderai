import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_error.dart';
import '../data/notification_models.dart';
import '../data/notification_repository.dart';

/// Default foreground auto-sync cycle for in-app notifications while authenticated.
const Duration kDefaultNotificationPollInterval = Duration(seconds: 2);

final bool _isFlutterWidgetTestRuntime =
    Platform.environment.containsKey('FLUTTER_TEST');

final notificationPollIntervalProvider = Provider<Duration?>((ref) {
  if (_isFlutterWidgetTestRuntime) return null;
  return kDefaultNotificationPollInterval;
});

final notificationRepositoryProvider = Provider<NotificationRepository>((ref) {
  return NotificationRepository(ref.watch(apiClientProvider));
});

List<AppNotificationModel> deduplicateNotifications(
  List<AppNotificationModel> raw,
) {
  final seenIds = <String>{};
  final seenInviteKeys = <String>{};
  final out = <AppNotificationModel>[];
  for (final item in raw) {
    final id = item.id.trim();
    if (id.isNotEmpty && !seenIds.add(id)) {
      continue;
    }
    if (item.isTripInvite) {
      final invId = item.effectiveInviteId?.trim();
      if (invId != null && invId.isNotEmpty && !seenInviteKeys.add(invId)) {
        continue;
      }
    }
    out.add(item);
  }
  return out;
}

class NotificationsState {
  final List<AppNotificationModel> items;
  final int unreadCount;
  final bool isLoading;
  final bool hasLoadedOnce;
  final String? errorMessage;

  const NotificationsState({
    this.items = const [],
    this.unreadCount = 0,
    this.isLoading = false,
    this.hasLoadedOnce = false,
    this.errorMessage,
  });

  NotificationsState copyWith({
    List<AppNotificationModel>? items,
    int? unreadCount,
    bool? isLoading,
    bool? hasLoadedOnce,
    String? errorMessage,
    bool clearError = false,
  }) {
    return NotificationsState(
      items: items ?? this.items,
      unreadCount: unreadCount ?? this.unreadCount,
      isLoading: isLoading ?? this.isLoading,
      hasLoadedOnce: hasLoadedOnce ?? this.hasLoadedOnce,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class NotificationsNotifier extends StateNotifier<NotificationsState> {
  final NotificationRepository _repo;
  int _sessionEpoch = 0;
  Future<void>? _inFlightLoad;

  NotificationsNotifier(this._repo) : super(const NotificationsState());

  void resetForLogout() {
    _sessionEpoch++;
    _inFlightLoad = null;
    state = const NotificationsState();
  }

  Future<void> load({bool silent = false}) {
    if (_inFlightLoad != null) {
      return _inFlightLoad!;
    }
    final epoch = _sessionEpoch;
    if (!silent) {
      state = state.copyWith(isLoading: true, clearError: true);
    }

    final future = () async {
      try {
        final res = await _repo.getNotifications();
        if (!mounted || epoch != _sessionEpoch) return;
        final deduped = deduplicateNotifications(res.items);
        state = state.copyWith(
          items: deduped,
          unreadCount: res.unreadCount,
          isLoading: false,
          hasLoadedOnce: true,
          clearError: true,
        );
      } on DioException catch (e) {
        if (!mounted || epoch != _sessionEpoch) return;
        if (!silent) {
          final details = ApiErrorDetails.fromDioException(e);
          state = state.copyWith(
            isLoading: false,
            errorMessage: details.message ??
                'Không thể tải danh sách thông báo. Vui lòng thử lại.',
          );
        } else {
          state = state.copyWith(isLoading: false);
        }
      } catch (_) {
        if (!mounted || epoch != _sessionEpoch) return;
        if (!silent) {
          state = state.copyWith(
            isLoading: false,
            errorMessage: 'Không thể tải danh sách thông báo.',
          );
        } else {
          state = state.copyWith(isLoading: false);
        }
      } finally {
        if (epoch == _sessionEpoch) {
          _inFlightLoad = null;
        }
      }
    }();

    _inFlightLoad = future;
    return future;
  }

  Future<void> markRead(String notificationId) async {
    final epoch = _sessionEpoch;
    final idx = state.items.indexWhere((n) => n.id == notificationId);
    if (idx >= 0 && !state.items[idx].isRead) {
      final updatedItems = List<AppNotificationModel>.from(state.items);
      updatedItems[idx] = updatedItems[idx].copyWith(isRead: true);
      final optimisticUnread =
          (state.unreadCount - 1) < 0 ? 0 : (state.unreadCount - 1);
      state = state.copyWith(
        items: updatedItems,
        unreadCount: optimisticUnread,
      );
    }
    try {
      final serverUnread = await _repo.markRead(notificationId);
      if (!mounted || epoch != _sessionEpoch) return;
      state = state.copyWith(unreadCount: serverUnread);
    } catch (_) {
      if (!mounted || epoch != _sessionEpoch) return;
      await load(silent: true);
    }
  }

  Future<void> markAllRead() async {
    final epoch = _sessionEpoch;
    final updatedItems =
        state.items.map((n) => n.copyWith(isRead: true)).toList();
    state = state.copyWith(items: updatedItems, unreadCount: 0);
    try {
      await _repo.markAllRead();
    } catch (_) {
      if (!mounted || epoch != _sessionEpoch) return;
      await load(silent: true);
    }
  }

  Future<({TripInviteDetailModel? invite, String? tripId, String? errorMessage})>
      acceptTripInvite(String inviteId) async {
    final epoch = _sessionEpoch;
    try {
      final res = await _repo.acceptTripInvite(inviteId);
      if (mounted && epoch == _sessionEpoch) {
        await load(silent: true);
      }
      return (invite: res.invite, tripId: res.tripId, errorMessage: null);
    } on DioException catch (e) {
      final details = ApiErrorDetails.fromDioException(e);
      if (mounted && epoch == _sessionEpoch) {
        await load(silent: true);
      }
      return (
        invite: null,
        tripId: null,
        errorMessage:
            details.message ?? 'Không thể chấp nhận lời mời lúc này.',
      );
    } catch (_) {
      return (
        invite: null,
        tripId: null,
        errorMessage: 'Không thể chấp nhận lời mời lúc này.',
      );
    }
  }

  Future<({TripInviteDetailModel? invite, String? errorMessage})>
      declineTripInvite(String inviteId) async {
    final epoch = _sessionEpoch;
    try {
      final updated = await _repo.declineTripInvite(inviteId);
      if (mounted && epoch == _sessionEpoch) {
        await load(silent: true);
      }
      return (invite: updated, errorMessage: null);
    } on DioException catch (e) {
      final details = ApiErrorDetails.fromDioException(e);
      if (mounted && epoch == _sessionEpoch) {
        await load(silent: true);
      }
      return (
        invite: null,
        errorMessage: details.message ?? 'Không thể từ chối lời mời lúc này.',
      );
    } catch (_) {
      return (
        invite: null,
        errorMessage: 'Không thể từ chối lời mời lúc này.',
      );
    }
  }
}

final notificationsProvider =
    StateNotifierProvider<NotificationsNotifier, NotificationsState>((ref) {
  return NotificationsNotifier(ref.watch(notificationRepositoryProvider));
});
