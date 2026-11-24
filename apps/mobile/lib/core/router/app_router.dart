import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../widgets/responsive_wrapper.dart';
import '../../features/auth/presentation/login_screen.dart';
import '../../features/auth/presentation/register_screen.dart';
import '../../features/auth/providers/auth_provider.dart';
import '../../features/home/presentation/home_screen.dart';
import '../../features/ai_chat/presentation/ai_chat_screen.dart';
import '../../features/trips/presentation/trip_list_screen.dart';
import '../../features/trips/presentation/trip_form_screen.dart';
import '../../features/trips/presentation/trip_detail_screen.dart';
import '../../features/map/presentation/map_screen.dart';
import '../../features/places/presentation/place_detail_screen.dart';
import '../../features/profile/presentation/preferences_screen.dart';
import '../../features/recommendations/presentation/recommendation_screen.dart';
import '../../features/safety/presentation/safety_and_buddies_screen.dart';
import '../session/session_reset.dart';

/// Explicit opt-in guest browse flag so cold-start `/` remains auth-gated by
/// default while allowing unauthenticated users to explore destinations/POIs.
final guestBrowseModeProvider = StateProvider<bool>((ref) => false);

/// Pending internal route to restore immediately after login/registration
/// (for example `/places/<placeId>` when an unauthenticated user taps Save).
final postLoginRedirectProvider = StateProvider<String?>((ref) => null);

/// Validates that a redirect target is a safe in-app path (blocks open redirects).
String? sanitizeInternalRedirect(String? raw) {
  if (raw == null) return null;
  final trimmed = raw.trim();
  if (trimmed.isEmpty || !trimmed.startsWith('/') || trimmed.startsWith('//')) {
    return null;
  }
  final parsed = Uri.tryParse(trimmed);
  if (parsed == null || parsed.hasScheme || parsed.hasAuthority) {
    return null;
  }
  if (parsed.path == '/login' || parsed.path == '/register') {
    return null;
  }
  return trimmed;
}

/// RouterNotifier listens to AuthState changes and triggers GoRouter redirect
/// without recreating the GoRouter or its Navigator GlobalKeys.
/// This completely resolves the "Multiple widgets used the same GlobalKey" exception.
class RouterNotifier extends ChangeNotifier {
  final Ref _ref;

  RouterNotifier(this._ref) {
    _ref.listen<AuthState>(
      authProvider,
      (previous, next) {
        // G-01: never carry one user's preferences/recommendations into the next session,
        // and never trigger session-scoped fetches during unauthenticated startup (unknown -> unauthenticated).
        if (previous?.status != next.status &&
            (previous?.status == AuthStatus.authenticated ||
                next.status == AuthStatus.authenticated)) {
          if (next.status == AuthStatus.authenticated) {
            _ref.read(guestBrowseModeProvider.notifier).state = false;
          } else {
            _ref.read(guestBrowseModeProvider.notifier).state = false;
            _ref.read(postLoginRedirectProvider.notifier).state = null;
          }
          resetSessionScopedState(
            _ref,
            isAuthenticated: next.status == AuthStatus.authenticated,
          );
        }
        notifyListeners();
      },
    );
    _ref.listen<bool>(guestBrowseModeProvider, (_, __) => notifyListeners());
  }

  String? redirect(BuildContext context, GoRouterState state) {
    final authState = _ref.read(authProvider);
    final isAuth = authState.status == AuthStatus.authenticated;
    final isLoading = authState.status == AuthStatus.unknown;
    final path = state.uri.path;
    final isLoginRoute = path == '/login' || path == '/register';

    // While loading auth state, don't redirect
    if (isLoading) return null;

    if (!isAuth) {
      if (isLoginRoute) return null;

      // Public place detail pages and explicit guest discovery routes are accessible pre-login.
      final isPublicPlaceDetail = path.startsWith('/places/');
      final isGuestShellAllowed =
          _ref.read(guestBrowseModeProvider) && (path == '/' || path == '/map');
      if (isPublicPlaceDetail || isGuestShellAllowed) {
        return null;
      }

      // Preserve non-root target route so login returns to the intended screen.
      final fullLocation = state.uri.toString();
      final safeTarget =
          fullLocation != '/' ? sanitizeInternalRedirect(fullLocation) : null;
      if (safeTarget != null) {
        return '/login?redirect=${Uri.encodeComponent(safeTarget)}';
      }
      return '/login';
    }

    // Authenticated on login/register → honor safe redirect back to POI/route, else home
    if (isLoginRoute) {
      return resolvePostAuthDestination(
        queryRedirect: state.uri.queryParameters['redirect'],
      );
    }

    return null;
  }

  /// Computes and consumes the post-login destination (`?redirect=...` or
  /// [postLoginRedirectProvider]), falling back to `'/'`.
  String resolvePostAuthDestination({String? queryRedirect}) {
    final fromQuery = sanitizeInternalRedirect(queryRedirect);
    final fromState =
        sanitizeInternalRedirect(_ref.read(postLoginRedirectProvider));
    final destination = fromQuery ?? fromState;
    if (fromState != null) {
      Future.microtask(() {
        _ref.read(postLoginRedirectProvider.notifier).state = null;
      });
    }
    return destination ?? '/';
  }
}

final routerNotifierProvider =
    Provider<RouterNotifier>((ref) => RouterNotifier(ref));

final appRouterProvider = Provider<GoRouter>((ref) {
  final notifier = ref.watch(routerNotifierProvider);
  final rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'rootNav');
  final shellNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'shellNav');

  return GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: '/',
    refreshListenable: notifier,
    redirect: notifier.redirect,
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => LoginScreen(
          redirectPath:
              sanitizeInternalRedirect(state.uri.queryParameters['redirect']),
        ),
      ),
      GoRoute(
        path: '/register',
        builder: (context, state) => RegisterScreen(
          redirectPath:
              sanitizeInternalRedirect(state.uri.queryParameters['redirect']),
        ),
      ),
      GoRoute(
        path: '/trips/create',
        builder: (context, state) => const TripFormScreen(),
      ),
      GoRoute(
        path: '/trips/:id',
        builder: (context, state) => TripDetailScreen(
          tripId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/places/:id',
        builder: (context, state) => PlaceDetailScreen(
          placeId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/profile/preferences',
        builder: (context, state) => const PreferencesScreen(),
      ),
      GoRoute(
        path: '/recommendations',
        builder: (context, state) => const RecommendationScreen(),
      ),
      ShellRoute(
        navigatorKey: shellNavigatorKey,
        builder: (context, state, child) => _MainScaffold(child: child),
        routes: [
          GoRoute(path: '/', builder: (_, __) => const HomeScreen()),
          GoRoute(path: '/map', builder: (_, __) => const MapScreen()),
          GoRoute(path: '/ai', builder: (_, __) => const AiChatScreen()),
          GoRoute(
              path: '/safety',
              builder: (_, __) => const SafetyAndBuddiesScreen()),
          GoRoute(path: '/trips', builder: (_, __) => const TripListScreen()),
        ],
      ),
    ],
  );
});

class _MainScaffold extends ConsumerWidget {
  final Widget child;
  const _MainScaffold({required this.child});

  static const _tabs = ['/', '/map', '/ai', '/safety', '/trips'];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Avoid mounting authenticated tab screens (and triggering pre-login /users/me calls)
    // before AuthNotifier finishes checking persisted tokens on startup.
    final authStatus = ref.watch(authProvider.select((s) => s.status));
    final isGuestBrowse = ref.watch(guestBrowseModeProvider);
    final path = GoRouterState.of(context).uri.path;
    final canRenderGuestTab = isGuestBrowse && (path == '/' || path == '/map');
    if (authStatus != AuthStatus.authenticated && !canRenderGuestTab) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    final currentIndex = _tabs.indexOf(path).clamp(0, 4);

    return Scaffold(
      body: child,
      bottomNavigationBar: Container(
        color: Theme.of(context).colorScheme.surface,
        child: SafeArea(
          top: false,
          child: ResponsiveWrapper(
            maxWidth: 720.0,
            fillHeight: false,
            child: NavigationBar(
              selectedIndex: currentIndex,
              onDestinationSelected: (index) {
                final targetTab = _tabs[index];
                if (authStatus != AuthStatus.authenticated &&
                    targetTab != '/' &&
                    targetTab != '/map') {
                  ref.read(postLoginRedirectProvider.notifier).state =
                      targetTab;
                  context.go(
                    '/login?redirect=${Uri.encodeComponent(targetTab)}',
                  );
                  return;
                }
                context.go(targetTab);
              },
              destinations: const [
                NavigationDestination(
                  icon: Icon(Icons.explore_outlined),
                  selectedIcon: Icon(Icons.explore),
                  label: 'Trang chủ',
                ),
                NavigationDestination(
                  icon: Icon(Icons.map_outlined),
                  selectedIcon: Icon(Icons.map),
                  label: 'Bản đồ',
                ),
                NavigationDestination(
                  icon: Icon(Icons.auto_awesome_outlined),
                  selectedIcon: Icon(Icons.auto_awesome),
                  label: 'Wandy AI',
                ),
                NavigationDestination(
                  icon: Icon(Icons.shield_outlined),
                  selectedIcon: Icon(Icons.shield),
                  label: 'An toàn',
                ),
                NavigationDestination(
                  icon: Icon(Icons.luggage_outlined),
                  selectedIcon: Icon(Icons.luggage),
                  label: 'Chuyến đi',
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
