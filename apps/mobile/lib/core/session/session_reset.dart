import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../features/profile/providers/profile_provider.dart';
import '../../features/recommendations/providers/recommendation_provider.dart';

/// Drops every provider that holds per-user data so the next signed-in user can
/// never see the previous user's state (preferences, recommendations).
///
/// PostgreSQL stays the single source of truth: invalidated providers simply
/// re-fetch from the backend with the new session's token. No second store.
void resetSessionScopedState(Ref ref) {
  ref.invalidate(profileProvider);
  ref.invalidate(recommendationProvider);
}
