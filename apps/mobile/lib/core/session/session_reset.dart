import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../features/ai_chat/providers/chat_provider.dart';
import '../../features/groups/providers/group_provider.dart';
import '../../features/home/providers/home_provider.dart';
import '../../features/profile/providers/profile_provider.dart';
import '../../features/recommendations/providers/recommendation_provider.dart';
import '../../features/safety/providers/buddy_provider.dart';
import '../../features/trips/providers/trip_provider.dart';

/// Drops or resets every provider that holds per-user data so the next
/// signed-in user can never see the previous user's state (preferences,
/// recommendations, AI chat, home, trips).
///
/// On logout (`isAuthenticated == false`), providers whose constructors fire
/// network calls (`/users/me`, `/trips`, `/destinations`) are reset in place
/// via `resetForLogout()` rather than invalidated, preventing spurious
/// unauthenticated 401 requests during router redirect to `/login`.
/// On login (`isAuthenticated == true`), existing providers are invalidated so
/// they re-fetch cleanly under the new session's token.
void resetSessionScopedState(Ref ref, {required bool isAuthenticated}) {
  if (isAuthenticated) {
    if (ref.exists(profileProvider)) {
      ref.invalidate(profileProvider);
    }
    if (ref.exists(recommendationProvider)) {
      ref.invalidate(recommendationProvider);
    }
    if (ref.exists(chatProvider)) {
      ref.invalidate(chatProvider);
    }
    if (ref.exists(homeProvider)) {
      ref.invalidate(homeProvider);
    }
    if (ref.exists(tripListProvider)) {
      ref.invalidate(tripListProvider);
    }
    if (ref.exists(tripDetailProvider)) {
      ref.invalidate(tripDetailProvider);
    }
    if (ref.exists(buddyProvider)) {
      ref.invalidate(buddyProvider);
    }
    if (ref.exists(groupListProvider)) {
      ref.invalidate(groupListProvider);
    }
    if (ref.exists(groupDetailProvider)) {
      ref.invalidate(groupDetailProvider);
    }
  } else {
    if (ref.exists(profileProvider)) {
      ref.read(profileProvider.notifier).resetForLogout();
    }
    if (ref.exists(recommendationProvider)) {
      ref.invalidate(recommendationProvider);
    }
    if (ref.exists(chatProvider)) {
      ref.read(chatProvider.notifier).resetForAuthTransition();
    }
    if (ref.exists(homeProvider)) {
      ref.read(homeProvider.notifier).resetForLogout();
    }
    if (ref.exists(tripListProvider)) {
      ref.read(tripListProvider.notifier).resetForLogout();
    }
    if (ref.exists(tripDetailProvider)) {
      ref.read(tripDetailProvider.notifier).resetForLogout();
    }
    if (ref.exists(buddyProvider)) {
      ref.read(buddyProvider.notifier).resetForLogout();
    }
    if (ref.exists(groupListProvider)) {
      ref.read(groupListProvider.notifier).resetForLogout();
    }
    if (ref.exists(groupDetailProvider)) {
      ref.read(groupDetailProvider.notifier).resetForLogout();
    }
  }
  ref.read(pendingChatPromptProvider.notifier).state = null;
}
