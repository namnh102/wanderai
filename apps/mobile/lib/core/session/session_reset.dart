import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../features/ai_chat/providers/chat_provider.dart';
import '../../features/home/providers/home_provider.dart';
import '../../features/profile/providers/profile_provider.dart';
import '../../features/recommendations/providers/recommendation_provider.dart';

/// Drops every provider that holds per-user data so the next signed-in user can
/// never see the previous user's state (preferences, recommendations, AI chat, home).
///
/// PostgreSQL stays the single source of truth: invalidated providers simply
/// re-fetch from the backend with the new session's token. No second store.
void resetSessionScopedState(Ref ref) {
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
  ref.read(pendingChatPromptProvider.notifier).state = null;
}
